CXX = hipcc
CXXFLAGS = -O3 -std=c++17 -fopenmp -Wno-unused-result
LIBS = -lhipblas

all: mlp_bp_dcu

mlp_bp_dcu: mlp_bp_dcu.o main_bp_dcu.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LIBS)

mlp_bp_dcu.o: mlp_bp_dcu.cpp mlp_bp_dcu.h
	$(CXX) $(CXXFLAGS) -c $< -o $@

main_bp_dcu.o: main_bp_dcu.cpp mlp_bp_dcu.h
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f mlp_bp_dcu *.o *.csv *.model

.PHONY: all clean
