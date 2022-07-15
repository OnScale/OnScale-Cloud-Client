import os
import time

import onscale_client as cloud


if __name__ == "__main__":

    # get file paths for input files
    directory = os.path.dirname(os.path.realpath(__file__))
    input_file = os.path.join(directory, "pzt_ring.flxinp")
    mat_file = os.path.join(directory, "pzt_ring.prjmat")

    # initialise the cloud client
    client = cloud.Client()

    # submit a job with specified
    new_job = client.submit(
        input_file=input_file,
        max_spend=5,
        other_files=[mat_file],
        job_name="flxinp_cloud_client",
        precision="DOUBLE",
        ram=2048,
        cores=2,
        core_hour_estimate=1,
        number_of_parts=1,
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
