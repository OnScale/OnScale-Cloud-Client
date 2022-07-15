"""
    Auto-generated simulation code.
"""
import onscale as on

with on.Simulation("Swing Arm", "None") as sim:

    # Define geometry
    geometry = on.CadFile("swing_arm_2.step")

    # Define material database and materials
    materials = on.CloudMaterials("onscale")
    steel = materials["steel"]
    steel >> geometry.parts[0]

    # Define and apply loads
    fixed = on.loads.Fixed()
    fixed >> geometry.parts[0].faces[496]
    fixed >> geometry.parts[0].faces[373]
    force = on.loads.Force(1000, [0, 0, -1])
    force >> geometry.parts[0].faces[340]
    force >> geometry.parts[0].faces[191]

    # Define meshing
    on.meshes.BasicMedium()

    # Define output variables
    on.outputs.Displacement()
    on.outputs.Stress()
    on.outputs.Strain()

import onscale_client as os_client
import time

client = os_client.Client()

# set account to desired account if required. See below
client.set_current_account(account_name="OnScale UK")

new_job = client.submit(
    input_obj=sim, max_spend=1, job_name=f"sim_submission_test_{time.time()}"
)

socket_thread = new_job.subscribe_to_progress()
