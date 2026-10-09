from prometheus_client import Counter,Histogram
REQUESTS=Counter('ecotwin_http_requests_total','HTTP requests',['method','route','status'])
LATENCY=Histogram('ecotwin_http_request_seconds','HTTP latency',['route'])
JOBS=Counter('ecotwin_simulation_jobs_total','Completed simulation attempts',['state'])
