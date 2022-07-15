import os
import time

import onscale_client as cloud


if __name__ == "__main__":

    # get file paths for input files
    directory = os.path.dirname(os.path.realpath(__file__))
    input_file = os.path.join(directory, "static_analysis.json")
    msh_file = os.path.join(directory, "Swing_Arm.step.bincad.msh")

    cloud.switch_default_profile("dev_1")

    # initialise the cloud client
    client = cloud.Client()

    # submit a job with specified
    new_job = client.submit(
        input_obj=input_file,
        max_spend=5,
        other_files=[msh_file],
        job_name="reflex_cloud_client",
        precision="DOUBLE",
        ram=16000,
        cores=4,
        core_hour_estimate=5,
        number_of_parts=2,
    )

    # if the job successfully committed poll status and progress
    if new_job is not None:
        status = new_job.status()
        while status != "FINISHED":
            print(f"waiting for {new_job.job_name}...")
            time.sleep(10)
            status = new_job.status()
            print(f"Progress: {new_job.get_progress()}")

        # download results
        new_job.download_results(os.path.join(directory, "downloads"))
