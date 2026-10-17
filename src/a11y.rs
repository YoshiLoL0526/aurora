//! Accesibilidad (AccessKit). La semántica que declara Python (`role`,
//! `label`, `checked`…) se convierte en el árbol nativo que ven los lectores
//! de pantalla: UIA en Windows, NSAccessibility en macOS y AT-SPI en Linux.
//!
//! Los nombres de rol son los de ARIA en minúscula (`"button"`, `"tablist"`).
//!
//! Aquí vive también el constructor del árbol (`build`): decide qué nodos
//! aparecen (los decorativos no), con qué rol (el declarado o uno por defecto
//! según el tipo), qué nombre, qué estados, qué bounds y qué acciones admiten.
//! Lo usan el adaptador de la ventana (`window.rs`) y el piloto (para tests).

use std::collections::HashMap;

use accesskit::{
    Action, Live, Node as AcNode, NodeId, Role, SortDirection, Toggled, TreeId, TreeInfo,
    TreeUpdate,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use skia_safe::Rect;

use crate::render::{Engine, HitRegion};
use crate::spec::{Kind, Node, Value};

/// Roles que entiende `role="…"`, ordenados como en AccessKit.
const ROLES: &[(&str, Role)] = &[
    ("alert", Role::Alert),
    ("alertdialog", Role::AlertDialog),
    ("article", Role::Article),
    ("banner", Role::Banner),
    ("button", Role::Button),
    ("canvas", Role::Canvas),
    ("cell", Role::Cell),
    ("checkbox", Role::CheckBox),
    ("columnheader", Role::ColumnHeader),
    ("combobox", Role::ComboBox),
    ("complementary", Role::Complementary),
    ("contentinfo", Role::ContentInfo),
    ("dialog", Role::Dialog),
    ("document", Role::Document),
    ("figure", Role::Figure),
    ("form", Role::Form),
    ("generic", Role::GenericContainer),
    ("grid", Role::Grid),
    ("gridcell", Role::GridCell),
    ("group", Role::Group),
    ("heading", Role::Heading),
    ("image", Role::Image),
    ("label", Role::Label),
    ("link", Role::Link),
    ("list", Role::List),
    ("listbox", Role::ListBox),
    ("listitem", Role::ListItem),
    ("main", Role::Main),
    ("menu", Role::Menu),
    ("menubar", Role::MenuBar),
    ("menuitem", Role::MenuItem),
    ("menuitemcheckbox", Role::MenuItemCheckBox),
    ("menuitemradio", Role::MenuItemRadio),
    ("meter", Role::Meter),
    ("navigation", Role::Navigation),
    ("option", Role::ListBoxOption),
    ("progressbar", Role::ProgressIndicator),
    ("radio", Role::RadioButton),
    ("radiogroup", Role::RadioGroup),
    ("region", Role::Region),
    ("row", Role::Row),
    ("rowheader", Role::RowHeader),
    ("scrollbar", Role::ScrollBar),
    ("scrollview", Role::ScrollView),
    ("search", Role::Search),
    ("searchbox", Role::SearchInput),
    ("section", Role::Section),
    ("separator", Role::Splitter),
    ("slider", Role::Slider),
    ("status", Role::Status),
    ("switch", Role::Switch),
    ("tab", Role::Tab),
    ("tablist", Role::TabList),
    ("tabpanel", Role::TabPanel),
    ("table", Role::Table),
    ("textarea", Role::MultilineTextInput),
    ("textbox", Role::TextInput),
    ("toolbar", Role::Toolbar),
    ("tooltip", Role::Tooltip),
    ("tree", Role::Tree),
    ("treeitem", Role::TreeItem),
    ("window", Role::Window),
];

/// El rol declarado con `role="…"`, o un error con los nombres válidos.
pub fn parse_role(name: &str) -> PyResult<Role> {
    let name = name.trim().to_ascii_lowercase();
    ROLES
        .iter()
        .find(|(n, _)| *n == name)
        .map(|(_, role)| *role)
        .ok_or_else(|| {
            let valid: Vec<&str> = ROLES.iter().map(|(n, _)| *n).collect();
            PyValueError::new_err(format!(
                "rol de accesibilidad desconocido: {name:?} (válidos: {})",
                valid.join(", ")
            ))
        })
}

/// La región viva declarada con `live="…"`: sus cambios se anuncian solos.
pub fn parse_live(name: &str) -> PyResult<Live> {
    match name.trim().to_ascii_lowercase().as_str() {
        "off" => Ok(Live::Off),
        "polite" => Ok(Live::Polite),
        "assertive" => Ok(Live::Assertive),
        other => Err(PyValueError::new_err(format!(
            "live desconocido: {other:?} (válidos: off, polite, assertive)"
        ))),
    }
}

/// La dirección declarada con `sort="…"`: una columna ordenada.
pub fn parse_sort(name: &str) -> PyResult<SortDirection> {
    match name.trim().to_ascii_lowercase().as_str() {
        "ascending" => Ok(SortDirection::Ascending),
        "descending" => Ok(SortDirection::Descending),
        other => Err(PyValueError::new_err(format!(
            "sort desconocido: {other:?} (válidos: ascending, descending)"
        ))),
    }
}

/// El nombre del rol, como lo escribe Python (`"button"`); para los que no
/// están en la tabla, el nombre de AccessKit en minúscula.
pub fn role_name(role: Role) -> String {
    ROLES
        .iter()
        .find(|(_, r)| *r == role)
        .map(|(n, _)| (*n).to_owned())
        .unwrap_or_else(|| format!("{role:?}").to_lowercase())
}

/// Id del nodo raíz: la ventana.
const WINDOW: NodeId = NodeId(0);

/// Estado de accesibilidad de un `Runtime`: el id estable de cada nodo (por su
/// key, como las animaciones) entre reconstrucciones.
#[derive(Default)]
pub struct A11y {
    ids: HashMap<String, u64>,
    next: u64,
}

impl A11y {
    /// Id estable de la key, asignado la primera vez que aparece.
    fn id(&mut self, key: &str) -> NodeId {
        if let Some(&raw) = self.ids.get(key) {
            return NodeId(raw);
        }
        self.next += 1;
        self.ids.insert(key.to_owned(), self.next);
        NodeId(self.next)
    }

    /// Id del nodo con esa key, si se registró alguna vez.
    pub fn node_id(&self, key: &str) -> Option<NodeId> {
        self.ids.get(key).map(|&raw| NodeId(raw))
    }

    /// Key del nodo con ese id.
    pub fn key_of(&self, id: NodeId) -> Option<&str> {
        self.ids
            .iter()
            .find(|(_, raw)| **raw == id.0)
            .map(|(key, _)| key.as_str())
    }
}

/// El árbol construido: la actualización completa para la plataforma y la key
/// de cada nodo incluido (para el piloto y los tests).
pub struct Built {
    pub update: TreeUpdate,
    pub keys: Vec<(NodeId, String)>,
}

/// Construye la actualización completa del árbol de la ventana. La raíz es la
/// ventana (id 0) y el nodo de la vista cuelga de ella. Cada nodo incluido
/// lleva su rol, su nombre, sus estados, sus bounds en píxeles físicos y las
/// acciones que admite; lo decorativo (una caja sin nada que anunciar, una
/// imagen sin `alt`) no aparece.
pub fn build(
    state: &mut A11y,
    tree: Option<&Node>,
    engine: &Engine,
    width: f32,
    height: f32,
    scale: f32,
) -> Built {
    let mut builder = Builder {
        state,
        engine,
        regions: engine.regions.iter().map(|r| (r.key.as_str(), r)).collect(),
        scale,
        focused: engine.focused.as_deref(),
        in_scroll: false,
        focus_id: WINDOW,
        nodes: Vec::new(),
        keys: Vec::new(),
    };
    let mut window = AcNode::new(Role::Window);
    window.set_bounds(accesskit::Rect::new(
        0.0,
        0.0,
        (width * scale) as f64,
        (height * scale) as f64,
    ));
    window.set_children(
        tree.and_then(|root| builder.node(root))
            .into_iter()
            .collect::<Vec<_>>(),
    );
    builder.nodes.push((WINDOW, window));
    let update = TreeUpdate {
        nodes: builder.nodes,
        tree: Some(TreeInfo {
            root: WINDOW,
            toolkit_name: Some("Aurora".to_owned()),
            toolkit_version: Some(env!("CARGO_PKG_VERSION").to_owned()),
        }),
        tree_id: TreeId::ROOT,
        focus: builder.focus_id,
    };
    Built {
        update,
        keys: builder.keys,
    }
}

/// Recorrido del árbol de la vista → nodos de AccessKit.
struct Builder<'a> {
    state: &'a mut A11y,
    engine: &'a Engine,
    /// Región de cada key (bounds y orden de pintura).
    regions: HashMap<&'a str, &'a HitRegion>,
    scale: f32,
    /// Key del nodo enfocado, si lo hay.
    focused: Option<&'a str>,
    /// Si algún ancestro de este nodo es un `scroll` (la acción «ver» lo usa).
    in_scroll: bool,
    focus_id: NodeId,
    nodes: Vec<(NodeId, AcNode)>,
    keys: Vec<(NodeId, String)>,
}

impl Builder<'_> {
    /// El nodo de accesibilidad de `node` con su subárbol, o `None` si todo él
    /// es decorativo (no se anuncia nada).
    fn node(&mut self, node: &Node) -> Option<NodeId> {
        if node.a11y.hidden {
            return None;
        }
        // Los hijos primero: un contenedor sin nada anunciable dentro tampoco
        // se anuncia (una caja de layout no es un nodo del árbol).
        let outer_scroll = self.in_scroll;
        if node.style.scroll.is_some() {
            self.in_scroll = true;
        }
        let mut children = Vec::new();
        for child in &node.children {
            if let Some(id) = self.node(child) {
                children.push(id);
            }
        }
        let scroll = node.style.scroll.is_some();
        self.in_scroll = outer_scroll;
        let meaningful = meaningful(node);
        if !meaningful && children.is_empty() {
            return None;
        }

        let mut ac = AcNode::new(role_of(node));
        if let Some(region) = self.regions.get(node.key.as_str()) {
            ac.set_bounds(physical(region.rect, self.scale));
        }
        let a = &node.a11y;
        if let Some(label) = &a.label {
            ac.set_label(label.clone());
        }
        if let Some(desc) = a.description.as_ref().or(node.style.tooltip.as_ref()) {
            ac.set_description(desc.clone());
        }
        match &a.value {
            Some(Value::Text(text)) => ac.set_value(text.clone()),
            Some(Value::Number(number)) => ac.set_numeric_value(*number),
            None => {}
        }
        // Un texto es su propio valor (los lectores lo anuncian así).
        if node.kind == Kind::Text
            && let Some(text) = &node.text
        {
            ac.set_value(text.clone());
        }
        if node.is_editable() {
            // Lo que se está escribiendo ahora mismo (el editor), no solo lo
            // que llegó de Python; y su pista si el campo está vacío.
            if let Some(state) = self.engine.inputs.get(&node.key) {
                ac.set_value(state.editor.text().to_owned());
            }
            if let Some(placeholder) = &node.style.placeholder {
                ac.set_placeholder(placeholder.clone());
            }
        }
        if let Some(checked) = a.checked {
            ac.set_toggled(if checked {
                Toggled::True
            } else {
                Toggled::False
            });
        }
        if let Some(selected) = a.selected {
            ac.set_selected(selected);
        }
        if let Some(expanded) = a.expanded {
            ac.set_expanded(expanded);
        }
        if let Some(live) = a.live {
            ac.set_live(live);
        }
        if let Some(level) = a.level {
            ac.set_level(level);
        }
        if let Some(position) = a.position_in_set {
            ac.set_position_in_set(position);
        }
        if let Some(size) = a.set_size {
            ac.set_size_of_set(size);
        }
        if let Some(sort) = a.sort {
            ac.set_sort_direction(sort);
        }
        if let Some(min) = a.value_min {
            ac.set_min_numeric_value(min);
        }
        if let Some(max) = a.value_max {
            ac.set_max_numeric_value(max);
        }
        if let Some(step) = a.value_step {
            ac.set_numeric_value_step(step);
        }
        if a.modal {
            ac.set_modal();
        }

        // Acciones que el núcleo sabe atender (ver `Runtime::a11y_action`).
        if node.handler("click").is_some() {
            ac.add_action(Action::Click);
        }
        if node.is_focusable() {
            ac.add_action(Action::Focus);
        }
        if node.is_editable() {
            ac.add_action(Action::SetValue);
        }
        // Solo los controles que se ajustan (no una barra de progreso).
        if matches!(ac.role(), Role::Slider | Role::SpinButton)
            && a.value_min.is_some()
            && a.value_max.is_some()
        {
            ac.add_action(Action::Increment);
            ac.add_action(Action::Decrement);
        }
        if let Some(expanded) = a.expanded {
            ac.add_action(if expanded {
                Action::Collapse
            } else {
                Action::Expand
            });
        }
        if (self.in_scroll || scroll) && !children.is_empty() {
            ac.add_action(Action::ScrollIntoView);
        }

        ac.set_children(children);
        let id = self.state.id(&node.key);
        if self.focused == Some(node.key.as_str()) {
            self.focus_id = id;
        }
        self.nodes.push((id, ac));
        self.keys.push((id, node.key.clone()));
        Some(id)
    }
}

/// Rol del nodo: el declarado, o el que corresponde a su tipo.
fn role_of(node: &Node) -> Role {
    if let Some(role) = node.a11y.role {
        return role;
    }
    match node.kind {
        Kind::Text => Role::Label,
        Kind::Input if node.style.multiline => Role::MultilineTextInput,
        Kind::Input => Role::TextInput,
        Kind::Image => Role::Image,
        Kind::Canvas => Role::Canvas,
        Kind::Chart => Role::Figure,
        Kind::Box if node.style.scroll.is_some() => Role::ScrollView,
        Kind::Box => Role::GenericContainer,
    }
}

/// Si el nodo anuncia algo por sí mismo (rol, nombre, estados, contenido,
/// interacción…). Una caja vacía no.
fn meaningful(node: &Node) -> bool {
    let a = &node.a11y;
    a.role.is_some()
        || a.label.is_some()
        || a.description.is_some()
        || a.value.is_some()
        || a.checked.is_some()
        || a.selected.is_some()
        || a.expanded.is_some()
        || a.live.is_some()
        || a.level.is_some()
        || a.position_in_set.is_some()
        || a.sort.is_some()
        || a.modal
        || node.handler("click").is_some()
        || node.is_focusable()
        || node.style.scroll.is_some()
        || node.style.tooltip.is_some()
        || match node.kind {
            Kind::Text => node.text.as_deref().is_some_and(|text| !text.is_empty()),
            Kind::Input | Kind::Canvas | Kind::Chart => true,
            // Una imagen sin `alt` es decorativa.
            Kind::Image | Kind::Box => false,
        }
}

/// El rectángulo en píxeles físicos (AccessKit usa los de la ventana).
fn physical(rect: Rect, scale: f32) -> accesskit::Rect {
    let s = scale as f64;
    accesskit::Rect::new(
        rect.left as f64 * s,
        rect.top as f64 * s,
        rect.right as f64 * s,
        rect.bottom as f64 * s,
    )
}

/// Acciones que se anuncian en el volcado, con su nombre para Python.
const ACTIONS: &[(Action, &str)] = &[
    (Action::Click, "click"),
    (Action::Focus, "focus"),
    (Action::SetValue, "set_value"),
    (Action::Increment, "increment"),
    (Action::Decrement, "decrement"),
    (Action::Expand, "expand"),
    (Action::Collapse, "collapse"),
    (Action::ScrollIntoView, "scroll_into_view"),
];

/// El árbol como lista de dicts (el piloto y los tests): `id`, `key`, `role`,
/// `label`, `value`, estados, `bounds` en píxeles lógicos, `actions`,
/// `children` y `focused`.
pub fn to_dicts<'py>(py: Python<'py>, built: &Built, scale: f32) -> PyResult<Bound<'py, PyList>> {
    let key_of: HashMap<NodeId, &str> = built
        .keys
        .iter()
        .map(|(id, key)| (*id, key.as_str()))
        .collect();
    let out = PyList::empty(py);
    for (id, node) in &built.update.nodes {
        let d = PyDict::new(py);
        d.set_item("id", id.0)?;
        d.set_item("key", key_of.get(id).copied().unwrap_or(""))?;
        d.set_item("role", role_name(node.role()))?;
        d.set_item("label", node.label())?;
        d.set_item("description", node.description())?;
        d.set_item("placeholder", node.placeholder())?;
        d.set_item("value", node.value())?;
        d.set_item("numeric_value", node.numeric_value())?;
        d.set_item("value_min", node.min_numeric_value())?;
        d.set_item("value_max", node.max_numeric_value())?;
        d.set_item("value_step", node.numeric_value_step())?;
        d.set_item(
            "checked",
            match node.toggled() {
                Some(Toggled::True) => Some(true),
                Some(Toggled::False) => Some(false),
                _ => None,
            },
        )?;
        d.set_item("selected", node.is_selected())?;
        d.set_item("expanded", node.is_expanded())?;
        d.set_item("level", node.level())?;
        d.set_item("position_in_set", node.position_in_set())?;
        d.set_item("set_size", node.size_of_set())?;
        d.set_item(
            "sort",
            node.sort_direction()
                .map(|s| format!("{s:?}").to_lowercase()),
        )?;
        d.set_item("modal", node.is_modal())?;
        d.set_item("bounds", node.bounds().map(|r| bounds(r, scale)))?;
        d.set_item(
            "actions",
            ACTIONS
                .iter()
                .filter(|(action, _)| node.supports_action(*action))
                .map(|(_, name)| *name)
                .collect::<Vec<_>>(),
        )?;
        d.set_item(
            "children",
            node.children()
                .iter()
                .map(|child| child.0)
                .collect::<Vec<_>>(),
        )?;
        let focused = *id == built.update.focus;
        d.set_item("focused", focused)?;
        out.append(d)?;
    }
    Ok(out)
}

/// Los bounds en píxeles lógicos, como los ve Python.
fn bounds(rect: accesskit::Rect, scale: f32) -> (f32, f32, f32, f32) {
    (
        rect.x0 as f32 / scale,
        rect.y0 as f32 / scale,
        rect.x1 as f32 / scale,
        rect.y1 as f32 / scale,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn los_roles_documentados_se_parsean() {
        assert_eq!(parse_role("button").unwrap(), Role::Button);
        assert_eq!(parse_role(" CheckBox ").unwrap(), Role::CheckBox);
        assert_eq!(parse_role("progressbar").unwrap(), Role::ProgressIndicator);
    }

    #[test]
    fn un_rol_desconocido_es_error() {
        assert!(parse_role("buton").is_err());
        assert!(parse_live("shouty").is_err());
        assert_eq!(parse_live("assertive").unwrap(), Live::Assertive);
    }
}
