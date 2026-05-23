CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -pedantic
CPPFLAGS ?=
LDFLAGS ?=

ifneq ("$(wildcard third_party/leveldb/build/libleveldb.a)","")
CPPFLAGS += -Ithird_party/leveldb/include -Ithird_party/leveldb
LDLIBS ?= third_party/leveldb/build/libleveldb.a -lpthread
else
LDLIBS ?= -lleveldb -lpthread
endif

TARGET := leveldb_lab
SRC := leveldb_test.cpp

.PHONY: all clean run_sample

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $< $(LDFLAGS) $(LDLIBS)

run_sample: $(TARGET)
	./$(TARGET) --mode=mixed --destroy_db=true --load_keys=10000 --num_keys=10000 --run_ops=20000 --value_size=1024 --output_prefix=results/sample

clean:
	rm -f $(TARGET)
