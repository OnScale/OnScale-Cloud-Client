"""
    Auto-generated simulation code.
"""
import onscale as on

with on.Simulation("None") as sim:

    # General simulation settings
    on.Scalar(length=1, time=0, mass=0)
    on.settings.DisabledPhysics(["thermal", "fluid", "electrical"])

    # Define geometry
    geometry = on.CadFile("box.SLDPRT")

    # Define material database and materials
    materials = on.CloudMaterials("onscale")
    alumina = materials["Alumina"]
    alumina >> geometry.parts[0]

    # Define and apply loads
    force = on.loads.Force(
        5000, [-0.0000000000000004440892098500626, 0, -1], alias="Force Load 1"
    )
    force >> geometry.parts[0].faces[3]
    restraint = on.loads.Restraint(x=True, y=True, z=True, alias="Fixture 1")
    restraint >> geometry.parts[0].faces[1]

    # Define meshing
    on.meshes.MeshFile("very_coarse_mesh_volume.msh")

    # Define output variables
    on.fields.PrincipalStrain()
    on.fields.Displacement()
    on.fields.Stress()
    on.fields.Strain()
    on.fields.VonMises()
    on.fields.PrincipalStress()
    probe = on.probes.ResultantForce(geometry.parts[0].faces[1])


import onscale_client as cloud
import time


client = cloud.Client()

lf = cloud.LinkedFile(
    job_id="866ed88d-531a-4cc0-8d02-6bda4c3ed524",
    file_name="very_coarse_mesh_volume.msh",
    file_alias="very_coarse_mesh_volume.msh",
)

new_job = client.submit(
    input_obj=sim,
    linked_files=[lf],
    max_spend=5,
    job_name=f"sim_submission_test_{time.time()}",
    hpc_cloud="AWS",
)
