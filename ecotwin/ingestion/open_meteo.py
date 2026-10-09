import math
from datetime import datetime,timezone,timedelta
from ecotwin.errors import TwinError

FIELDS={'temperature_2m':('temperature_c','°C'),'relative_humidity_2m':('humidity_pct','%'),'precipitation':('rain_mm','mm'),'wind_speed_10m':('wind_mps','m/s'),'shortwave_radiation':('ghi_w_m2','W/m²')}
URL='https://api.open-meteo.com/v1/forecast'

def fetch_weather(client,latitude,longitude,hours=72):
    if not 1<=hours<=384:
        raise TwinError('MODEL_INPUT_UNSUPPORTED','Forecast hours must be 1–384')
    return client.json(URL,params={'latitude':latitude,'longitude':longitude,'hourly':','.join(FIELDS),'timezone':'UTC','forecast_hours':hours,'wind_speed_unit':'ms','temperature_unit':'celsius','precipitation_unit':'mm'})

def parse_weather(document,issued_at):
    try:
        hourly,units=document['hourly'],document['hourly_units']
        times=hourly['time']
        if not times or len(times)>384 or any(len(hourly[key])!=len(times) or units[key]!=unit for key,(_,unit) in FIELDS.items()):
            raise ValueError('Arrays or units mismatch')
        result=[]
        previous=None
        for index,value in enumerate(times):
            valid=datetime.fromisoformat(value.replace('Z','+00:00'))
            if not valid.tzinfo:
                valid=valid.replace(tzinfo=timezone.utc)
            if previous and valid-previous!=timedelta(hours=1):
                raise ValueError('Noncontiguous hourly time axis')
            previous=valid
            row={'valid_at':valid,'issued_at':issued_at,'source_lat':document['latitude'],'source_lon':document['longitude'],'model_name':document.get('model','best_match')}
            for key,(name,_) in FIELDS.items():
                item=hourly[key][index]
                if item is not None and (not isinstance(item,(int,float)) or not math.isfinite(item)):
                    raise ValueError('Nonfinite measurement')
                row[name]=item
            if any(row[k] is not None and row[k]<0 for k in ['rain_mm','ghi_w_m2','wind_mps']) or row['humidity_pct'] is not None and not 0<=row['humidity_pct']<=100:
                raise ValueError('Invalid weather range')
            result.append(row)
        return result
    except (ValueError,KeyError,TypeError) as exc:
        raise TwinError('UPSTREAM_PAYLOAD_INVALID','Invalid Open-Meteo units, time axis or readings') from exc
