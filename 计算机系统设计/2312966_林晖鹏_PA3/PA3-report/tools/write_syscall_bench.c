#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static long long now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

int main(int argc, char *argv[]) {
  size_t total = 1024 * 1024;
  size_t chunk = 1;

  if (argc >= 2) {
    total = strtoull(argv[1], NULL, 10);
  }
  if (argc >= 3) {
    chunk = strtoull(argv[2], NULL, 10);
  }

  if (chunk == 0 || total == 0) {
    fprintf(stderr, "usage: %s [total_bytes] [chunk_size]\n", argv[0]);
    return 1;
  }

  char *buf = malloc(chunk);
  if (buf == NULL) {
    perror("malloc");
    return 1;
  }
  memset(buf, 'A', chunk);

  size_t written = 0;
  long long start = now_ns();

  while (written < total) {
    size_t this_time = chunk;
    if (this_time > total - written) {
      this_time = total - written;
    }

    ssize_t ret = write(STDOUT_FILENO, buf, this_time);
    if (ret < 0) {
      perror("write");
      free(buf);
      return 1;
    }
    written += (size_t)ret;
  }

  long long end = now_ns();
  double ms = (end - start) / 1000000.0;

  dprintf(STDERR_FILENO,
    "\n[bench] total=%zu bytes, chunk=%zu bytes, calls=%zu, time=%.3f ms\n",
    total, chunk, (total + chunk - 1) / chunk, ms);

  free(buf);
  return 0;
}
