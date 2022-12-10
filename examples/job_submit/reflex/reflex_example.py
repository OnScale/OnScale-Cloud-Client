import os
import sys
import time

import onscale_client as cloud


if __name__ == "__main__":

    # get file paths for input files
    directory = os.path.dirname(os.path.realpath(__file__))
    input_file = os.path.join(directory, "static_analysis.json")
    msh_file = os.path.join(directory, "Swing_Arm.step.bincad.msh")

    # profile = "test"
    # ret = cloud.switch_default_profile(profile)
    # if ret != 0:
    #   print("cannot use profile alias '%s'" % profile)
    #   sys.exit(1)

    # initialise the cloud client
    try:
        client = cloud.Client(debug_mode = False)
    except:
        print("error: cannot create client")
        sys.exit(1)

    # submit a job with specified reflex JSON input file
    try:
        job = client.submit(
            input_obj=input_file,
            max_spend=5,
            other_files=[msh_file],
            job_name="reflex_cloud_client",
            precision="DOUBLE",
            ram=16000,
            cores=4,
            core_hour_estimate=1.0,
            number_of_parts=2
        )
    except:
        print("error: cannot submit job")
        sys.exit(1)
        
    # if the job successfully committed poll status and progress
    print(f"waiting for {job.job_name} with id {job.job_id}...")
    status = job.status()
    while status != "FINISHED":
        time.sleep(10)
        status = job.status()
        print(f"{status}--{job.get_progress()}%")

    # download results
    job.download_results(os.path.join(directory, "downloads"))
    print("results donwloaded in directory 'downloads'")
