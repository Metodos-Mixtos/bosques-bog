# Sistema Monitoreo de Bosques y Páramos de Bogotá (SIMBYP)

Este repositorio contiene herramientas y scripts para el análisis y monitoreo de los bosques en Bogotá, integrando diversas fuentes de datos satelitales y funcionalidades para el seguimiento de la cobertura terrestre y la deforestación.

## Estructura del Repositorio

- `dynamic_world/`: Scripts para el análisis de cobertura terrestre con Dynamic World.
Este proyecto descarga los mapas de cobertura terrestre de Dynamic World disponibles en 
Google Earth Engine para dos trimestres de referencia y un área definida.

Además, crea una grilla de 100 m × 100 m sobre el área de estudio para calcular estadísticas 
zonales de ambos periodos y estimar el cambio porcentual entre ellos. Finalmente, genera un mapa de coberturas del suelo para los dos trimestres seleccionados.

- `gfw_alert/`:   Se conecta a la API de Global Forest Watch (GFW) para descargar alertas integradas 
  de deforestación que combinan tres subsistemas: GLAD-L, GLAD-S2 y RADD, según una fecha y un polígono 
  definidos. 

  El script guarda los resultados en un archivo CSV, genera un archivo JSON con el resumen estadístico 
  por tipo de alerta, y crea un mapa mostrandos las alertas en el área de referencia.

  Frecuencia: Puede correrse mensual. Es la información más frecuente. Trimestral puede ser ideal.

- `notebooks_de_referencia`: Códigos sueltos o viejos que pueden ser útiles para algunas funciones específicas, como descargar imágenes de Planet, cuando estén disponibles.

Frecuencia: no se corre regularmente. Es código útil para temas específicos. 

- `sentinel-images-download/`: Código para la descarga y procesamiento de imágenes satelitales Sentinel. Otros submódulos y utilidades relacionadas con el monitoreo de bosques.

Frecuencia: este no se corre en sí mismo. Se llama desde otros módulos y corre en la medida en se corran otros módulos. 

- `urban_sprawl/`: Herramientas para analizar la expansión urbana y su impacto sobre los bosques, utilizando datos de Dynamic World y comparativas temporales.

Frecuencia: se corre semestralmente, en julio y en enero idealmente. 

## Uso

Consulta los README específicos de cada subcarpeta para instrucciones detalladas sobre instalación y uso.

## Colaboradores

Este proyecto es mantenido por el equipo de Métodos Mixtos y colaboradores (Daniel Wiesner, Javier Guerra y Laura Tamayo).  
Para sugerencias o reportar problemas, crea un Issue o Pull Request.

## Data sources

- Las bases de datos están en Teams en en el canal GIS en
- data_folder = 'GIS/geoinfo/Colombia/Bogotá/bosques_bogota'
- 'https://metodosmixtos.sharepoint.com/:f:/s/MMC-General/EogKVdk7FYZBsTKCr79IK98BgnozkrY1czyiyR6MDn5i5g?e=78hsPW'

### Set-up

- python3 -m venv .venv
- source .venv/bin/activate
- pip install --upgrade pip setuptools wheel
- pip install -r requirements.txt

- El .env file hay que crearlo con la información que está en: 
'MMC - General - SDP - Monitoreo de Bosques/monitoreo_bosques/dot_env_content.txt'

## Licencia

La licencia es pública. El código es de propiedad de la Secretaría Distrital de Planeación de Bogotá.