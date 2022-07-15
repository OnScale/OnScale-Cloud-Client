"""
    Auto-generated code for MOEBIUS postprocessing

    Run as: mpirun -np X python3 -m mpi4py moebius_postprocess.py
"""
import TOOLS.ClipMeshBySurfaceFine as clip
import vtk
import os
from mpi4py import MPI


if __name__ == "__main__":

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    numprocs = comm.Get_size()

    surfFilename = "result_surface_mesh.vtp"
    LTCName = "/tmp/template.ltc"

    if rank == 0:
        print("Postprocessing starts ...")

    if not os.path.isfile(surfFilename):
        print("surface vtp file not found")
        exit(1)

    if not os.path.isdir(LTCName):
        print("/tmp/template.ltc not found")
        exit(1)

    surfF = vtk.vtkXMLPolyDataReader()
    surfF.SetFileName(surfFilename)
    surfF.Update()

    t = vtk.vtkTransform()
    t.Scale(1.0e-3, 1.0e-3, 1.0e-3)
    tF = vtk.vtkTransformPolyDataFilter()
    tF.SetInputConnection(surfF.GetOutputPort())
    tF.SetTransform(t)
    tF.Update()

    clip.setBC(ioid=1, bctype="pressure", val=0)
    clip.setBC(
        ioid=2, bctype="velocity", val_dir=[-1.0, 1.394229542445967e-17, 0.0], val=1
    )

    clip.processLTC(tF, LTCName, 1)

    MPI.Finalize()
