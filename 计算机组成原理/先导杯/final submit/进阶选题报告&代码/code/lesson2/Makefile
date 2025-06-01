CXX = hipcc
CXXFLAGS = -std=c++17
LDFLAGS = -lhipblas -fopenmp

# 基础版本目标
BASE_SRCS = mlp_dcu.cpp main.cpp
BASE_OBJS = $(BASE_SRCS:.cpp=.o)
BASE_TARGET = mlp_forward

# 优化版本目标
OPT_SRCS = mlp_dcu_optimized.cpp main_optimized.cpp
OPT_OBJS = $(OPT_SRCS:.cpp=.o)
OPT_TARGET = mlp_forward_optimized

.PHONY: all base optimized clean

all: base optimized

base: $(BASE_TARGET)

optimized: $(OPT_TARGET)

$(BASE_TARGET): $(BASE_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(OPT_TARGET): $(OPT_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(BASE_OBJS) $(OPT_OBJS) $(BASE_TARGET) $(OPT_TARGET) *.csv
	rm -rf results
