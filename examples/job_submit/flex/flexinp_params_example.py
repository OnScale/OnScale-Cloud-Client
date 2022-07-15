import os
import time

import onscale_client as cloud

import onscale
from onscale.visitors.parameter import ParameterSweep


RAM = 2048
CORES = 4
PARTS = 2
CH_ESTIMATE = 1

if __name__ == "__main__":

    # get file paths for input files
    directory = os.path.dirname(os.path.realpath(__file__))
    input_file = os.path.join(directory, "pzt_ring.flxinp")
    mat_file = os.path.join(directory, "pzt_ring.prjmat")
    other_files = list()

    # set up the parameter sweep values -
    # This is only one way to do this. The parameter values are
    # specified as strings on the command line, so that can be done
    # in any fashion as long as the format is : '-s $symbx_param_name=$value'
    symbx_map = {
        "pzt_thk": [2e-3, 2.1e-3, 2.2e-3, 2.3e-3, 2.4e-3, 2.5e-3],
        "vel": [2000, 2100, 2200, 2300, 2400, 2500],
    }

    sim_params = list()
    sweep = ParameterSweep(symbx_map)
    names = sweep.names()
    if names:
        for row in sweep:
            args = [f"-s {name}={value}" for name, value in zip(names, row)]
            sim_params.append(args)

    # initialise the cloud client
    client = cloud.Client()

    print(f"current account: {client.current_account_name}")

    # create a job
    job = client.create_job(
        job_name="flex_params_test",
        simulation_count=sweep.sim_count,
        operation="SIMULATION",
    )

    # upload input files
    job.upload_file(input_file)
    job.upload_file(mat_file)

    for f in other_files:
        job.upload_file(f)

    # calculate the console parameters list
    console_parameters = f"-mem mb {RAM} {0.1*RAM} -noterm -mp {CORES} stat "

    # generate the simulations for the job
    sim_list = list()
    for i, params in enumerate(sim_params):
        # create the list of params
        str = " ".join(params)
        sim = cloud.Simulation.get_default_sim_data(
            job.job_id,
            client.current_account_id,
            index=i,
            console_parameters=console_parameters + str,
        )
        sim_list.append(sim)

    # submit the job
    job.submit(
        job_type="simulation",
        main_file=os.path.basename(input_file),
        ram_estimate=RAM,
        cores_required=CORES,
        core_hour_estimate=CH_ESTIMATE,
        number_of_parts=PARTS,
        operation="SIMULATION",
        precision="SINGLE",
        docker_tag="barra",
        simulations=sim_list,
        simulation_count=len(sim_list),
    )
