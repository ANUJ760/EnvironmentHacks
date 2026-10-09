MODELS={
 'landcover_summary':{'version':'landcover-v1','required_inputs':['worldcover'],'evidence_class':'DETERMINISTIC_CALCULATION'},
 'runoff_screen':{'version':'runoff-coeff-v1','required_inputs':['worldcover','event_rainfall_mm'],'evidence_class':'SCREENING_ESTIMATE'},
 'solar_pv':{'version':'solar-screen-v1','required_inputs':['weather','pv_parameters'],'evidence_class':'SCREENING_ESTIMATE'},
 'waste_balance':{'version':'legacy-waste-v1','required_inputs':['waste'],'evidence_class':'DETERMINISTIC_CALCULATION'},
}
UNSUPPORTED=['heat_delta','pm25_delta','biodiversity','flood_inundation','grid_power_flow','health_incidence']
