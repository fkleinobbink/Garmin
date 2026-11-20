curl -sS -m 60 --data-urlencode 'data=[out:json][timeout:50];(way["name"~"Brettenpad|Overbrakerpad"](52.375,4.77,52.40,4.88););out geom;' https://overpass-api.de/api/interpreter -o fetch/out/bretten.json
curl -sS -m 60 --data-urlencode 'data=[out:json][timeout:50];(way["highway"](52.383,4.80,52.392,4.87););out geom;' https://overpass-api.de/api/interpreter -o fetch/out/area.json
