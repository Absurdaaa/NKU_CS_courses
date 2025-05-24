mpic++ -fopenmp -o outputfile sourcefile.cpp

./outputfile baseline >>all_result.out

./outputfile openmp >>all_result.out

./outputfile block >>all_result.out

mpirun --allow-run-as-root -np 4 ./outputfile mpi >>all_result.out

# dcu
hipcc sourcefile_dcu.cpp -o outputfile_dcu

./outputfile_dcu >>all_result.out