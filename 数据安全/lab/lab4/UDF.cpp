#include "Node.h"
#if defined(__has_include)
#  if __has_include(<mysql/mysql.h>)
#    include <mysql/mysql.h>
#  elif __has_include(<mysql.h>)
#    include <mysql.h>
#  else
typedef struct {
  unsigned int arg_count;
  char **args;
  unsigned long *lengths;
} UDF_ARGS;

typedef struct {
  void *ptr;
} UDF_INIT;
#  endif
#else
typedef struct {
  unsigned int arg_count;
  char **args;
  unsigned long *lengths;
} UDF_ARGS;

typedef struct {
  void *ptr;
} UDF_INIT;
#endif
#include <string.h>

extern "C"
{
// 插入
bool FHInsert_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHInsert(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
// 搜索
bool FHSearch_init(UDF_INIT *const initid, UDF_ARGS *const args, char *const message);
long long FHSearch(UDF_INIT *const initid, UDF_ARGS *const args,
char *const result, unsigned long *const length,
char *const is_null, char *const error);

// 更新
bool FHUpdate_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHUpdate(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
// 更新范围
bool FHStart_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHStart(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
bool FHEnd_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHEnd(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
// 调试开关
bool FHSetDebug_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHSetDebug(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
// 统计计数器
bool FHGetRebalanceCnt_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHGetRebalanceCnt(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
bool FHGetRecodeCnt_init(UDF_INIT *initid, UDF_ARGS *args, char *message);
long long FHGetRecodeCnt(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error);
}
static char * getba(UDF_ARGS *const args, int i, double &len) {
len = args->lengths[i];
return args->args[i];
}
/*插入*/
long long FHInsert(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
int pos = *(int *)(args->args[0]);
double keyLen;

char *const keyBytes = getba(args, 1, keyLen);
const std::string cipher = std::string(keyBytes, keyLen);
long long start_update = -1;
long long end_update = -1;
update.clear();
long long re = root->insert(pos, cipher);
return re;
}
bool FHInsert_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
start_update = -1;
end_update = -1;
update.clear();
if (root == nullptr)
{
root_initial();
}
return 0;
}

/*搜索*/
long long FHSearch(UDF_INIT *const initid, UDF_ARGS *const args, char *const result,   unsigned long *const length, char *const is_null, char *const error)
{
int pos = *(int *)(args->args[0]);
if (pos < 0)
return 0;
return root->search(pos);
}
bool FHSearch_init(UDF_INIT *const initid, UDF_ARGS *const args, char *const message) {
return 0;
}
long long FHUpdate(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
double keyLen;
char *const keyBytes = getba(args, 0, keyLen);
const std::string cipher = std::string(keyBytes, keyLen);
long long update_code = get_update(cipher);
return update_code;
}
bool FHUpdate_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
return 0;
}
long long FHStart(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
return start_update;
}
bool FHStart_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
return 0;
}

long long FHEnd(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
return end_update;
}
bool FHEnd_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
return 0;
}

/*调试开关: FHSetDebug(1) 开启, FHSetDebug(0) 关闭*/
long long FHSetDebug(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
int flag = *(int *)(args->args[0]);
debug_enabled = (flag != 0);
if (debug_enabled) {
fprintf(stderr, "[FHOPE-DEBUG] Debug logging enabled\n");
}
return debug_enabled ? 1 : 0;
}
bool FHSetDebug_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
return 0;
}

/*查询 rebalance 次数*/
long long FHGetRebalanceCnt(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
return (long long)rebalance_cnt;
}
bool FHGetRebalanceCnt_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
return 0;
}

/*查询 recode 次数*/
long long FHGetRecodeCnt(UDF_INIT *initid, UDF_ARGS *args, char *is_null, char *error) {
return (long long)recode_cnt;
}
bool FHGetRecodeCnt_init(UDF_INIT *initid, UDF_ARGS *args, char *message) {
return 0;
}
