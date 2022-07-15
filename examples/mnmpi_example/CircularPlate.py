"""
    Auto-generated simulation code.
"""
import onscale as on

with on.Simulation("None", "None") as sim:

    # General simulation settings
    on.Scalar(length=1, time=0, mass=0)

    # Define geometry
    geometry = on.CadFile("CircPlate_Quarter.step")

    # Define material database and materials
    materials = on.CloudMaterials("onscale")
    high_strength_alloy_steel = materials["High-strength alloy steel"]
    high_strength_alloy_steel >> geometry.parts[0]

    # Define and apply loads
    pressure = on.loads.Pressure(250e3, alias="LoadedArea")
    pressure >> geometry.parts[0].faces[2]
    restraint = on.loads.Restraint(x=True, y=True, z=True, alias="CircumFace")
    restraint >> geometry.parts[0].faces[4]
    symmetry = on.loads.Symmetry(alias="NXFace")
    symmetry >> geometry.parts[0].faces[5]
    symmetry_2 = on.loads.Symmetry(alias="NYFace")
    symmetry_2 >> geometry.parts[0].faces[3]

    # Define probes
    probe1 = on.Probe([55.0272, 59.3952, 1.5])
    on.kpis.Displacement(probe1)
    probe2 = on.Probe([35.7692, 12.0066, 1.5])
    on.kpis.Displacement(probe2)

    # Define meshing
    on.meshes.BasicCoarse()

    # Define output variables
    on.outputs.Displacement()
    on.outputs.Stress()
    on.outputs.Strain()
    on.outputs.VonMises()
    on.kpis.ResultantForce([geometry.parts[0].faces[4]])

import onscale_client as client
import time

client = client.Client()
client.set_current_account(account_name="OnScale UK")

# set account to desired account if required. See below
# client.set_current_account(account_name='OnScale US')

new_job = client.submit(
    input_obj=sim,
    max_spend=5,
    job_name=f"sim_submission_test_{time.time()}",
    docker_tag="cloud-develop",
    number_of_parts=60,
)

# new_job = client.submit(input_obj=sim,
#                        max_spend=5,
#                        job_name=f"sim_submission_test_{time.time()}")
