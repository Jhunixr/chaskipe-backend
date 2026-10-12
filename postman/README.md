# Pruebas de Postman — backend de Chaski Pe

Archivos:

- `chaskipe-backend.postman_collection.json`: 28 peticiones con 48 pruebas.
- `local.postman_environment.json`: `baseUrl` = `http://localhost:8000`.
- `vps.postman_environment.json`: pon en `baseUrl` el dominio de tu backend en Dokploy.

## Como usarlas

1. En Postman: **Import** y arrastra los 3 archivos.
2. Arriba a la derecha elige el entorno (**Chaski Pe — vps** o **— local**).
3. Clic derecho en la coleccion → **Run collection** → **Run**.

Las peticiones van en orden. El registro crea una cuenta nueva en cada corrida
(`postman_<fecha>@prueba.chaskipe.pe`) y guarda el token para las siguientes.

## Que revisa

| Carpeta | Pruebas |
| --- | --- |
| 0. Estado | `/health` responde, usa **PostgreSQL** (no memoria) y tarda menos de 2 s |
| 1. Cuenta | registro (201), correo repetido (409), clave corta (422), login (200), clave mala (401), `/me` con y sin token |
| 2. Perfil y preferencias | ver y cambiar nombre; ver, guardar y rechazar preferencias invalidas |
| 3. Historial | agregar, listar, rechazar datos invalidos, borrar (204), borrar de nuevo (404), vaciar |
| 4. Contenido publico | frases, vocabulario de senas, una sena, sena inexistente (404), modelos, reporte de reconocimiento |
| 5. Dataset | resumen; rechaza muestras sin consentimiento (422) y exportar sin token de admin (403). No sube datos. |

## Ojo

- Cada corrida deja en la base de datos una cuenta de prueba, un reporte de
  reconocimiento y el cambio de preferencias de esa cuenta. El historial de
  prueba se borra al final.
- En local, sin PostgreSQL, el backend usa memoria y la prueba "usa PostgreSQL"
  falla a proposito: en el VPS tiene que pasar.
- Desde la terminal: `npx newman run chaskipe-backend.postman_collection.json -e vps.postman_environment.json`
