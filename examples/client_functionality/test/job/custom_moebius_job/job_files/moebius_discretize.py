"""
    Auto-generated code for MOEBIUS Discretizer

    Run as: mpirun -np X python3 -m mpi4py moebius_discretize.py

"""
import Discretizer
import argparse
import os
import vtk
import numpy
from mpi4py import MPI


def discretize():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--spacing",
        required=True,
        default=None,
        help="finest voxel spacing in meters",
    )
    parser.add_argument(
        "-l",
        "--lchar",
        required=False,
        default=None,
        help="characteristic length in meters",
    )
    parser.add_argument(
        "-C",
        "--continueOnVersionMismatch",
        required=False,
        action="store_true",
        help="continue on ltu/backend version mismatch",
    )
    parser.add_argument(
        "-D",
        "--debugMode",
        required=False,
        action="store_false",
        help="run in debug mode",
    )
    parser.add_argument(
        "-P",
        "--progressReport",
        required=False,
        action="store_false",
        help="Progress report in json format",
    )
    args = parser.parse_args()

    sVTP = "boundary_mesh.vtp"
    dVTP = "/tmp/template.ltu/scale_0/geometry_0/geometry_0.vtp"

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()

    if rank == 0:
        reader = vtk.vtkXMLPolyDataReader()
        reader.SetFileName(sVTP)
        reader.Update()

        t = vtk.vtkTransform()
        t.Scale(1.0e-3, 1.0e-3, 1.0e-3)
        tF = vtk.vtkTransformPolyDataFilter()
        tF.SetInputConnection(reader.GetOutputPort())
        tF.SetTransform(t)
        tF.Update()

        writer = vtk.vtkXMLPolyDataWriter()
        writer.SetFileName(dVTP)
        writer.SetInputConnection(tF.GetOutputPort())
        writer.Update()

        f = open("/tmp/template.ltu/scale_0/fluid_0/BC/bgkflag.ios", "w")
        f.write("2\n")
        f.write("1 outlet pressure  0 0 0  0 0 0  1.  geometry_0 TBA 1. Vchar\n")
        f.write("2 inlet velocity  0 0 0  0 0 0  1.  geometry_0 TBA 1. Vchar\n")
        f.close()

    comm.barrier()

    spc = float(args.spacing)
    Discretizer.go(
        deviceFile=dVTP, spacing=spc, output="/tmp/template.ltu/scale_0/vmesh_0/bgkflag"
    )


if __name__ == "__main__":
    discretize()
