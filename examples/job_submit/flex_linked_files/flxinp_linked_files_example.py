import os

import onscale_client as cloud


if __name__ == "__main__":

    # get file paths for input files
    directory = os.path.dirname(os.path.realpath(__file__))
    input_file = os.path.join(directory, "pzt_ring.flxinp")
    mat_file = os.path.join(directory, "pzt_ring.prjmat")

    # initialise the cloud client
    client = cloud.Client()

    lf = cloud.LinkedFile(
        job_id="710c771b-3ebf-4344-9ce0-ba2feb123956",
        file_name="pzt_ring.prjmat",
        file_alias="pzt_ring.prjmat",
    )

    # submit a job with specified
    new_job = client.submit(
        input_obj=input_file,
        max_spend=5,
        linked_files=[lf],
        job_name="flxinp_linked_files_example",
        precision="DOUBLE",
        ram=2048,
        cores=2,
        core_hour_estimate=1,
        number_of_parts=1,
    )
