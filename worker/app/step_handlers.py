def run_ingestion(config):
    print(f"Running Ingestion with config: {config}")

def run_validation(config):
    print(f"Running Validation with config: {config}")
    
def run_transformation(config):
    print(f"Running Transformation with config: {config}")

def run_load(config):
    print(f"Running Load with config: {config}")

def run_observability_recording(config):
    print(f"Running Observability Recording with config: {config}")

step_registry={"ingestion":run_ingestion,
               "validation":run_validation,
               "transformation":run_transformation,
               "load":run_load,
               "observability_recording":run_observability_recording}
