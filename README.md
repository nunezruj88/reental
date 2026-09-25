# Reental

Aplicación para un LXC Linux con Nginx, accesible desde la red local en **http://10.8.1.106:8082**. Si cambia la IP del LXC, usar `http://IP_DEL_LXC:8082`. No requiere dominio, DNS ni Cloudflare Tunnel. La aplicación utiliza su propio sitio Nginx y mantiene separada la web de `/var/www/periodico`.

## Qué incluye

- Resumen responsive con recuentos, cobertura de relaciones y ranking por número de registros de alquiler.
- Carga conjunta y validada de ambos CSV; reemplazo atómico en SQLite, conservando el conjunto anterior ante errores de validación.
- Explorador con todas las columnas originales, búsqueda, paginación y grupos de registros relacionados.
- Compras: clave de primera columna. Alquiler: texto anterior al primer `#` de primera columna. Se recortan espacios exteriores, se conservan ceros iniciales y mayúsculas. Las claves vacías no coinciden. Los duplicados se muestran y no multiplican los recuentos.
- UTF-8/BOM o Windows-1252, separadores `, ; TAB |`, valores entrecomillados y multilínea. Se exige cabecera única y no vacía. Máximo 10 MB, 50.000 filas y 150 columnas por archivo.
- Persistencia del último conjunto válido; no incluye histórico de importaciones ni cuentas individuales. El acceso compartido se protege con contraseña en Nginx.

Se revisaron los CSV reales: contienen inversiones por inmueble y distribuciones de rendimientos. El dashboard añade sumas de `inversion`, `distributed`, `reinvested`, `claimed` y `retained`, gráficos por inmueble y mes, y avisos de fechas inconsistentes. Los cálculos usan decimales exactos en el backend y nunca suman `distributed` con su posible desglose. Los valores vacíos o inválidos hacen que el total afectado aparezca como no disponible, no como cero. Los CSV originales no están incluidos en el paquete.

Los importes están en dólares estadounidenses (USD) y `periodo` se expresa en meses. Si `inicio rendimientos` está vacío (o solo contiene espacios), el rendimiento se obtiene al final del periodo; no se considera una fecha errónea. Las fechas no vacías con formato incorrecto siguen generando un aviso. No se inventa una fecha de vencimiento ni se confunde ausencia de registros con rendimiento cero. Queda pendiente confirmar si los campos de retorno son porcentajes; se muestran sus valores originales, sin previsiones ni beneficio neto. Los recuentos de alquiler son filas, no se presupone que cada fila sea una transacción. Las rutas, usuario y servicio usan el nombre `reental`.

## Arquitectura y aislamiento

```text
Red local → IP_DEL_LXC:8082 (Nginx) → 127.0.0.1:8091
                                            └─ /var/www/reental
Datos: /var/lib/reental/reental.sqlite3
Servicio: reental.service · Usuario: reental
```

Nginx escucha en el puerto **8082**, que distingue Reental del periódico. El backend escucha únicamente en **127.0.0.1:8091**; desde otro equipo se accede al 8082. Se conserva la contraseña de Nginx. La configuración no añade ninguna escucha en el puerto 80 ni sustituye el sitio predeterminado. Comprobar que 8082 y 8091 estén libres antes de la primera instalación.

El acceso HTTP está pensado para una red local de confianza. No crear redirecciones de puertos en el router ni rutas públicas de Tunnel para Reental. Si hay firewall en el LXC o Proxmox, permitir TCP 8082 solo desde la red local real; no es necesario exponer 8091. `server_name _` admite el acceso por IP, pero no es una restricción de red.

## Prueba local (Python 3.10 o posterior)

Desde esta carpeta:

```sh
python -m unittest discover -s tests -v
python app.py
```

Abrir `http://127.0.0.1:8091`. El servidor local es solo para pruebas; en Linux se usa Gunicorn. Los archivos CSV no se sirven como archivos públicos. No usar datos reales en una publicación sin protección de acceso y HTTPS.

## Obtener el repositorio desde el LXC

Abrir una consola dentro del LXC que aloja Nginx, desde el panel del servidor o por SSH con su dirección y usuario habituales. Ejecutar los siguientes comandos como `root` (si se entra con otro usuario administrador, ejecutar primero `sudo -i`).

Instalar Git y descargar la rama `main` del repositorio:

```sh
apt-get update
apt-get install -y git ca-certificates
git clone --branch main https://github.com/nunezruj88/reental.git /tmp/reental
cd /tmp/reental
git log -1 --oneline
ls
```

Deberían aparecer `README.md`, `app.py`, `finance.py`, `requirements.txt` y las carpetas `static`, `deploy` y `tests`. La descarga se hace en `/tmp/reental`; no modifica `/var/www/periodico` ni activa ningún sitio de Nginx. `/tmp` es una ubicación temporal: la instalación siguiente copia el código a `/var/www/reental`.

Si `/tmp/reental` ya existe, no borrarlo ni repetir la clonación encima. Comprobar primero que corresponde a este repositorio y que no hay cambios locales:

```sh
git -C /tmp/reental remote -v
git -C /tmp/reental status --short
```

Si el remoto es `https://github.com/nunezruj88/reental.git` y el estado está limpio, actualizar esa copia con:

```sh
git -C /tmp/reental pull --ff-only origin main
```

Si hay cambios locales o el directorio corresponde a otro proyecto, conservarlo y revisar antes de continuar. Actualizar `/tmp/reental` solo actualiza la copia descargada, no la aplicación instalada.

Si el repositorio es público, la clonación por HTTPS no requiere iniciar sesión. Si es privado, GitHub requiere una cuenta con acceso y un token de acceso personal al pedir la contraseña; la contraseña normal de GitHub no sirve. No incluir el token en la URL ni guardarlo en este README.

Continuar con la sección siguiente para instalar lo descargado.

## Instalación en Debian/Ubuntu: revisar primero

Ejecutar en el LXC como administrador, después de descargar el repositorio en `/tmp/reental` siguiendo la sección anterior. Los comandos de instalación presuponen que las rutas y el usuario de Reental no existen todavía; si existen, revisar antes de copiar. No tocar los archivos del periódico.

```sh
ss -ltnp 'sport = :8091'
ss -ltnp 'sport = :8082'
nginx -t
nginx -T > /root/nginx-antes-reental.txt 2>&1
```

Si 8091 está ocupado por otro servicio, elegir un puerto libre y cambiarlo tanto en `deploy/reental.service` como en `proxy_pass` de `deploy/reental.nginx.conf`. Si 8082 está ocupado por otro sitio, cambiar `listen` en la plantilla Nginx y el puerto de la URL de acceso. Si Reental ya está instalado, es normal que sus propios procesos ocupen esos puertos. Guardar también una respuesta HTTP de la web existente usando su dirección habitual, para compararla después.

```sh
apt-get install python3-venv apache2-utils curl
useradd --system --home /var/lib/reental --shell /usr/sbin/nologin reental
install -d -m 755 /var/www/reental
cp -r /tmp/reental/. /var/www/reental/
python3 -m venv /var/www/reental/.venv
/var/www/reental/.venv/bin/pip install -r /var/www/reental/requirements.txt
cp /var/www/reental/deploy/reental.service /etc/systemd/system/reental.service
systemctl daemon-reload
systemctl enable --now reental
curl --fail http://127.0.0.1:8091/health
```

El servicio crea su directorio privado de datos mediante `StateDirectory`. El código permanece propiedad del administrador. Ver registros con `journalctl -u reental -n 50`.

## Acceso por IP y puerto con Nginx

La plantilla `deploy/reental.nginx.conf` ya contiene `listen 8082;`, `server_name _;` y el proxy hacia `127.0.0.1:8091`. No hay que introducir un dominio ni la IP en esa plantilla. Nginx debe incluir `sites-enabled` (distribuciones Debian/Ubuntu habituales).

Crear la contraseña solo si aún no existe el fichero y activar únicamente el sitio Reental:

```sh
if [ ! -f /etc/nginx/reental.htpasswd ]; then
    htpasswd -c /etc/nginx/reental.htpasswd administrador
fi
chown root:www-data /etc/nginx/reental.htpasswd
chmod 640 /etc/nginx/reental.htpasswd
cp /var/www/reental/deploy/reental.nginx.conf /etc/nginx/sites-available/reental
if [ ! -e /etc/nginx/sites-enabled/reental ] && [ ! -L /etc/nginx/sites-enabled/reental ]; then
    ln -s /etc/nginx/sites-available/reental /etc/nginx/sites-enabled/reental
fi
nginx -t
```

Usar el grupo real de los trabajadores de Nginx si no es `www-data`. No reutilizar `htpasswd -c` en futuras actualizaciones: recrearía ese fichero de contraseñas.

**Solo si `nginx -t` termina correctamente**, recargar sin reiniciar:

```sh
systemctl reload nginx
curl -I http://127.0.0.1:8082/
curl --fail -u administrador http://127.0.0.1:8082/health
```

La primera petición debe devolver 401 y la segunda, tras introducir contraseña, `{"status":"ok"}`. Desde otro equipo de la red abrir **http://10.8.1.106:8082** (o la IP actual del LXC) e iniciar sesión con `administrador` y su contraseña. Confirmar que el periódico sigue respondiendo como antes y probar una carga de CSV.

## Actualizar una instalación existente al acceso local

Si el acceso por `IP:8082` ya funciona con la misma configuración, no hace falta cambiar el servicio ni volver a crear usuario, contraseña o base de datos. Para aplicar la plantilla del repositorio a una instalación que aún usa el dominio, descargar la versión actual en `/tmp/reental` siguiendo la sección de Git y ejecutar:

```sh
cp -a /etc/nginx/sites-available/reental /etc/nginx/reental.before-lan.conf
cp /tmp/reental/deploy/reental.nginx.conf /etc/nginx/sites-available/reental
nginx -t && systemctl reload nginx
```

Si la comprobación falla, no recargar Nginx: restaurar la copia con `cp /etc/nginx/reental.before-lan.conf /etc/nginx/sites-available/reental` y revisar el error. La actualización de esta configuración no modifica datos ni archivos del periódico. Si se había publicado Reental mediante un Tunnel o una redirección del router, retirar únicamente esa ruta pública; conservar las rutas de los demás servicios.

## Copia y retirada

Antes de reemplazar datos importantes, hacer copia consistente con Python/SQLite backup o con `sqlite3 /var/lib/reental/reental.sqlite3 ".backup '/ruta/privada/reental-backup.sqlite3'"`. Mantener privada la copia. La importación sustituye el conjunto anterior y no guarda histórico.

Para desactivar únicamente Reental: quitar el enlace `/etc/nginx/sites-enabled/reental`, ejecutar `nginx -t` y, si pasa, recargar Nginx; después `systemctl disable --now reental`. Conservar el directorio de datos. No eliminar ni editar otros sitios.

Referencia oficial usada para la configuración: https://nginx.org/en/docs/http/ngx_http_proxy_module.html y https://nginx.org/en/docs/http/server_names.html.
