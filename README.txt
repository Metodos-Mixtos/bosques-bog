Este proyecto analiza la deforestación en los bosques de la ciudad de Bogotá
Creado por Daniel Wiesner y Javier Guerra
2024

#Las bases de datos están en Teams en en el canal GIS en
#data_folder = 'GIS/geoinfo/Colombia/Bogotá/bosques_bogota'
#'https://metodosmixtos.sharepoint.com/:f:/s/MMC-General/EogKVdk7FYZBsTKCr79IK98BgnozkrY1czyiyR6MDn5i5g?e=78hsPW'

Para instalar el ambiente de programación, lo mejor es: 

conda deactivate #Si usa conda 

cd 'carpeta del proyecto'
python -m venv bosques_env
source bosques_env/bin/activate
pip install -r requirements.txt

El .env file hay que crearlo con la información que está en: 
'MMC - General - SDP - Monitoreo de Bosques/monitoreo_bosques/dot_env_content.txt'

----------

Proyecto gfw_alerts

Este proyecto se conecta a la API de Global Forest Watch (GFW) para descargar alertas integradas 
de deforestación que combinan tres subsistemas: GLAD-L, GLAD-S2 y RADD, según una fecha y un polígono 
definidos.

El script guarda los resultados en un archivo CSV, genera un archivo JSON con el resumen estadístico 
por tipo de alerta, y crea un mapa mostrandos las alertas en el área de referencia.

------------

Proyecto dynamic_world

Este proyecto descarga los mapas de cobertura terrestre de Dynamic World disponibles en 
Google Earth Engine para dos trimestres de referencia y un área definida.

Además, crea una grilla de 100 m × 100 m sobre el área de estudio para calcular estadísticas 
zonales de ambos periodos y estimar el cambio porcentual entre ellos. Finalmente, genera un mapa
de coberturas del suelo para los dos trimestres seleccionados.

