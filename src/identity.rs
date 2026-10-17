//! Identidad de la app en Windows: su **AppUserModelID** (AUMID).
//!
//! Windows atribuye las notificaciones (y agrupa la barra de tareas) por
//! AUMID, no por proceso: sin uno propio, `notify-rust` usa el AUMID de
//! reserva de PowerShell y el aviso sale como «Windows PowerShell». Para que
//! Windows acepte un AUMID propio en una app sin instalador hace falta además
//! un **acceso directo del menú Inicio** con esa identidad: `register` lo crea
//! (y lo actualiza si el ejecutable cambió de sitio). Fuera de Windows, no-op.

use std::path::{Path, PathBuf};

use pyo3::prelude::*;

/// Fija la identidad del proceso (barra de tareas, agrupación, avisos).
pub fn set(app_id: &str) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        windows_impl::set(app_id)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = app_id;
        Ok(())
    }
}

/// Registra la identidad con un acceso directo del menú Inicio.
///
/// Devuelve `true` si lo dejó registrado (o ya estaba al día) y `false` si la
/// plataforma no lo necesita (fuera de Windows).
pub fn register(
    app_id: &str,
    name: &str,
    target: &Path,
    arguments: Option<&str>,
) -> Result<bool, String> {
    #[cfg(target_os = "windows")]
    {
        windows_impl::register(app_id, name, target, arguments)?;
        Ok(true)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (app_id, name, target, arguments);
        Ok(false)
    }
}

/// Fija la identidad de la app (AUMID) en el proceso. Los fallos, por stderr.
#[pyfunction]
pub fn app_id_set(app_id: &str) {
    if let Err(err) = set(app_id) {
        eprintln!("aurora: no se pudo fijar la identidad de la app: {err}");
    }
}

/// Registra la identidad con un acceso directo del menú Inicio (Windows).
/// Devuelve `false` fuera de Windows o si no se pudo; el motivo, por stderr.
#[pyfunction]
#[pyo3(signature = (app_id, name, target, arguments = None))]
pub fn app_id_register(
    app_id: String,
    name: String,
    target: PathBuf,
    arguments: Option<String>,
) -> bool {
    match register(&app_id, &name, &target, arguments.as_deref()) {
        Ok(done) => done,
        Err(err) => {
            eprintln!("aurora: no se pudo registrar la identidad de la app: {err}");
            false
        }
    }
}

/// El nombre de archivo del acceso directo (`Memoria.txt` → `Memoria.txt.lnk`).
/// Los caracteres que Windows no admite en un nombre se cambian por `-`.
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
fn safe_name(name: &str) -> String {
    let clean: String = name
        .chars()
        .map(|c| if r#"\/:*?"<>|"#.contains(c) { '-' } else { c })
        .collect();
    let clean = clean.trim();
    if clean.is_empty() {
        "Aurora".to_string()
    } else {
        clean.to_string()
    }
}

#[cfg(target_os = "windows")]
mod windows_impl {
    use std::path::{Path, PathBuf};

    use windows::Win32::Foundation::PROPERTYKEY;
    use windows::Win32::System::Com::StructuredStorage::{
        PROPVARIANT, PROPVARIANT_0, PROPVARIANT_0_0, PROPVARIANT_0_0_0, PropVariantClear,
    };
    use windows::Win32::System::Com::{
        CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED, CoCreateInstance, CoInitializeEx,
        CoTaskMemAlloc, IPersistFile, STGM_READ,
    };
    use windows::Win32::System::Variant::VT_LPWSTR;
    use windows::Win32::UI::Shell::PropertiesSystem::IPropertyStore;
    use windows::Win32::UI::Shell::{
        IShellLinkW, SetCurrentProcessExplicitAppUserModelID, ShellLink,
    };
    use windows::core::{GUID, HSTRING, Interface, PCWSTR, PWSTR};

    use super::safe_name;

    /// `PKEY_AppUserModel_ID` (propkey.h): la identidad en un acceso directo.
    const PKEY_APP_USER_MODEL_ID: PROPERTYKEY = PROPERTYKEY {
        fmtid: GUID::from_u128(0x9F4C2855_9F79_4B39_A8D0_E1D42DE1D5F3),
        pid: 5,
    };

    /// Fija el AUMID del proceso.
    pub fn set(app_id: &str) -> Result<(), String> {
        let id = HSTRING::from(app_id);
        unsafe { SetCurrentProcessExplicitAppUserModelID(PCWSTR(id.as_ptr())) }
            .map_err(|err| err.to_string())
    }

    /// Crea (o actualiza) el acceso directo del menú Inicio con la identidad.
    pub fn register(
        app_id: &str,
        name: &str,
        target: &Path,
        arguments: Option<&str>,
    ) -> Result<(), String> {
        let lnk = shortcut_path(name)?;
        if up_to_date(&lnk, app_id, target) {
            return Ok(());
        }
        if let Some(parent) = lnk.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|err| format!("no se pudo preparar el menú Inicio: {err}"))?;
        }
        unsafe { create(&lnk, app_id, target, arguments) }
    }

    /// `%APPDATA%\Microsoft\Windows\Start Menu\Programs\<nombre>.lnk`.
    fn shortcut_path(name: &str) -> Result<PathBuf, String> {
        let appdata = std::env::var_os("APPDATA")
            .ok_or_else(|| "no hay APPDATA en el entorno".to_string())?;
        Ok(PathBuf::from(appdata)
            .join("Microsoft")
            .join("Windows")
            .join("Start Menu")
            .join("Programs")
            .join(format!("{}.lnk", safe_name(name))))
    }

    /// ¿El acceso directo ya apunta a este ejecutable con esta identidad?
    fn up_to_date(lnk: &Path, app_id: &str, target: &Path) -> bool {
        lnk.exists() && unsafe { read_matches(lnk, app_id, target) }.unwrap_or(false)
    }

    unsafe fn shell_link() -> windows::core::Result<IShellLinkW> {
        // En el hilo principal winit ya inicializó COM; fuera de él, esto lo hace.
        let _ = unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) };
        unsafe { CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER) }
    }

    unsafe fn create(
        lnk: &Path,
        app_id: &str,
        target: &Path,
        arguments: Option<&str>,
    ) -> Result<(), String> {
        let message = |err: windows::core::Error| err.to_string();
        let link = unsafe { shell_link() }.map_err(message)?;
        let exe = HSTRING::from(target.to_string_lossy().as_ref());
        let wide: Vec<u16> = app_id.encode_utf16().chain([0]).collect();
        // El PROPVARIANT va con la cadena en memoria de COM: el almacén de
        // propiedades se queda con ella y la libera él (con memoria de Rust,
        // la liberación corrompía el montón).
        let buffer = unsafe { CoTaskMemAlloc(wide.len() * 2) } as *mut u16;
        if buffer.is_null() {
            return Err("sin memoria para la identidad".into());
        }
        unsafe { std::ptr::copy_nonoverlapping(wide.as_ptr(), buffer, wide.len()) };
        let identity = PROPVARIANT {
            Anonymous: PROPVARIANT_0 {
                Anonymous: std::mem::ManuallyDrop::new(PROPVARIANT_0_0 {
                    vt: VT_LPWSTR,
                    wReserved1: 0,
                    wReserved2: 0,
                    wReserved3: 0,
                    Anonymous: PROPVARIANT_0_0_0 {
                        pwszVal: PWSTR(buffer),
                    },
                }),
            },
        };
        unsafe {
            link.SetPath(&exe).map_err(message)?;
            link.SetIconLocation(&exe, 0).map_err(message)?;
            link.SetDescription(&HSTRING::from(app_id))
                .map_err(message)?;
            if let Some(arguments) = arguments {
                link.SetArguments(&HSTRING::from(arguments))
                    .map_err(message)?;
            }
            let store: IPropertyStore = link.cast().map_err(message)?;
            store
                .SetValue(&PKEY_APP_USER_MODEL_ID, &identity)
                .map_err(message)?;
            store.Commit().map_err(message)?;
            let file: IPersistFile = link.cast().map_err(message)?;
            let path = HSTRING::from(lnk.to_string_lossy().as_ref());
            file.Save(&path, true).map_err(message)?;
        }
        Ok(())
    }

    unsafe fn read_matches(
        in_lnk: &Path,
        app_id: &str,
        target: &Path,
    ) -> windows::core::Result<bool> {
        let link = unsafe { shell_link() }?;
        let file: IPersistFile = link.cast()?;
        let path = HSTRING::from(in_lnk.to_string_lossy().as_ref());
        unsafe { file.Load(&path, STGM_READ) }?;
        let mut buffer = [0u16; 1024];
        unsafe { link.GetPath(&mut buffer, std::ptr::null_mut(), 0) }?;
        let end = buffer.iter().position(|c| *c == 0).unwrap_or(buffer.len());
        let current = String::from_utf16_lossy(&buffer[..end]);
        if !current.eq_ignore_ascii_case(&target.to_string_lossy()) {
            return Ok(false);
        }
        let store: IPropertyStore = link.cast()?;
        let mut identity = unsafe { store.GetValue(&PKEY_APP_USER_MODEL_ID) }?;
        let registered = unsafe { wide_to_string(identity.Anonymous.Anonymous.Anonymous.pwszVal) };
        // El PROPVARIANT devuelto reserva la cadena: hay que soltarla.
        let _ = unsafe { PropVariantClear(&mut identity) };
        Ok(registered.as_deref() == Some(app_id))
    }

    /// Lee una cadena ancha terminada en cero (de un PROPVARIANT con `VT_LPWSTR`).
    unsafe fn wide_to_string(value: PWSTR) -> Option<String> {
        if value.is_null() {
            return None;
        }
        let mut len = 0usize;
        unsafe {
            while *value.0.add(len) != 0 {
                len += 1;
            }
            Some(String::from_utf16_lossy(std::slice::from_raw_parts(
                value.0, len,
            )))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::safe_name;

    #[test]
    fn shortcut_names_lose_the_characters_windows_hates() {
        assert_eq!(safe_name("Aurora: notas/Grandes"), "Aurora- notas-Grandes");
        assert_eq!(safe_name("  "), "Aurora");
        assert_eq!(safe_name("Notas.txt"), "Notas.txt");
    }
}
