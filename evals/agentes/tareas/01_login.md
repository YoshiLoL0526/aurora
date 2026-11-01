# Formulario de acceso

Escribe en `app.py` una app de Aurora con un formulario de acceso.

- Un campo de correo con `key="email"` y otro de contraseña con `key="password"`.
- Un botón «Entrar» con `key="submit"`.
- Al pulsar «Entrar»:
  - si el correo no contiene `@`, se muestra el texto `Email inválido`;
  - si la contraseña tiene menos de 6 caracteres (y el correo es válido), se muestra
    `Contraseña demasiado corta`;
  - si todo es válido, el formulario se sustituye por el texto `Bienvenido, <correo>`
    (por ejemplo `Bienvenido, ana@ejemplo.com`).
- Tiene que verse bien en una ventana de 480×520.
