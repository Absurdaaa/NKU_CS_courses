#include<iostream>
#include<vector>
using namespace std;
# define w_n 5 // 大作业个数
# define v_n 8 // 前置视频个数
# define work_time 4 // 完成一个大作业的基础时间
# define video_time 2 // 观看一个前置视频的基础时间
# define T 30 // 期末前的剩余时间
# define m 11 // 前置关系数
# define work_score 30 // 每个大作业的分数
# define video_score 5 // 每个视频的分数
# define review_score 7 // 复习一天能获得的分数
# define basis_score 300 // 基础分数


/**
 * 变量说明：
 * v_n:前置视频个数
 * w_n:大作业个数
 * m:前置关系数
 * work_time:完成大作业的基础时间
 * video_time:观看前置视频的基础时间
 * T:期末前的剩余时间
 * 
 * 注意编号从1开始，前w_n个编号为大作业，后v_n个编号为视频
 */

// bool mp[w_n + v_n + 1][w_n + v_n + 1]; // 前置关系矩阵，mp[i][j]表示任务i是否是任务j的前置任务

struct state
{
  state()
  {
    day = 0;
    for (int i = 1; i < w_n + v_n + 1; i++)
    {
      st[i] = false; // 初始化状态数组为未完成
      skip[i] = false; // 初始化跳过状态数组为未跳过
    }
    score =(-work_score * w_n) + (-video_score * v_n); // 初始得分
  }

  int day;
  bool st[w_n + v_n + 1]; // 状态数组，记录视频和大作业的完成情况
  int score;              // 当前状态的得分
  vector<int> can_do;     // 可以完成的任务列表(这里放非跳过的)
  vector<int> can_skip;   // 可以跳过的任务列表(这里放跳过的)
  bool skip[w_n + v_n + 1]; // 跳过状态数组，记录视频和大作业的跳过情况
}; // 状态结构体

// 希望用一个node图结构来记录关系，快速判断是否有前置任务未完成
struct Node
{
  int id; // 任务编号
  bool is_video;
  int out;
  vector<int> next; // 后续任务列表
  int in;
  vector<int> pre; // 前置任务列表
}; // 任务结构体

state dp[30];
Node nodes[w_n + v_n + 1]; // 任务列表，编号从1到w_n + v_n

void update_can_do(vector<int> &can_do, state &s, int task_id);

void init(){
  for(int i=0;i<m;i++){
    int x,y;    //x->y
    cin>>x>>y;
    // mp[x][y] = true;
    nodes[x].next.push_back(y); // 将y添加到x的后续任务列表
    nodes[y].pre.push_back(x); // 将x添加到y的前置任务列表
    nodes[y].in++; // y的前置任务数量增加
    nodes[x].out++; // x的后续任务数量增加
    
    nodes[x].id = x; // 设置任务编号
    nodes[y].id = y; // 设置任务编号
    nodes[x].is_video = (x > w_n); // 判断是否为视频任务
    nodes[y].is_video = (y > w_n); // 判断是否为视频任务
  }
  vector<int> can_do; // 可以完成的任务列表
  vector<int> can_skip; // 可以跳过的任务列表
  // 初始化可以完成的任务列表
  for(int i=1;i<=w_n+v_n;i++){
    if(nodes[i].in == 0){
      can_do.push_back(i); // 如果没有前置任务，则可以完成
    }
    else{
      bool can = 1; // 是否可以提前完成该任务
      for(vector<int>::iterator it = nodes[i].pre.begin(); it != nodes[i].pre.end(); it++){
        int pre_task = *it; // 前置任务编号
        if(nodes[pre_task].in != 0) { //前面还有前置
          can = 0;
          break;
        }
      }
      if(can)can_skip.push_back(i); // 如果可以提前完成，则添加到可以完成的任务列表
    }
  }
  //初始化状态
  for(int i = 0; i < 30; i++) {
    dp[i] = state(); // 每一天的状态初始化
    dp[i].day = i; // 设置当前天数
    dp[i].can_do = can_do; // 设置可以完成的任务列表
    dp[i].can_skip = can_skip; // 设置可以跳过的任务列表
    
  }
}

int main(){
  init();
  
  for(int i = 0;i<30;i++){
    for(vector<int>::iterator it = dp[i].can_do.begin(); it != dp[i].can_do.end(); it++){
      int task_id = *it;           // 当前任务编号
      if(dp[i].st[task_id]) continue; // 如果当前任务已经完成，则跳过
      Node &task = nodes[task_id]; // 获取当前任务节点

      state new_state = dp[i]; // 复制当前状态

      new_state.st[task_id] = true; // 标记当前任务已完成
      new_state.can_do.erase(new_state.can_do.begin()+(it-dp[i].can_do.begin())); // 从可以完成的任务列表中移除当前任务

      if(task.is_video) {
        new_state.score += video_score; // 如果是视频任务，增加视频分数
        new_state.day += video_time; // 增加观看视频的时间
      } else {
        new_state.score += work_score; // 如果是大作业，增加大作业分数
        new_state.day += work_time; // 增加完成大作业的时间
      }
      
      update_can_do(new_state.can_do, new_state, task_id); // 更新可以完成的任务列表
      
      if(new_state.day > T) continue; // 如果超过期末前的剩余时间，则跳过该状态
      dp[new_state.day] = dp[new_state.day].score > new_state.score ? dp[new_state.day] : new_state; // 更新状态
    }
    
    for(vector<int>::iterator it = dp[i].can_skip.begin(); it != dp[i].can_skip.end(); it++){
      int task_id = *it;           // 当前任务编号
      if(dp[i].st[task_id]) continue; // 如果当前任务已经完成，则跳过
      Node &task = nodes[task_id]; // 获取当前任务节点
      state new_state = dp[i];     // 复制当前状态

      new_state.st[task_id] = true; // 标记当前任务已完成
      
      int skip_num = 0; // 跳过的任务数量
      for(int j = 0; j < task.in; j++) {
        if(!new_state.st[task.pre[j]]) { // 如果前置任务未完成
          skip_num++; // 跳过的任务数量增加
          new_state.st[task.pre[j]] = true; // 标记所有前置任务已完成
          new_state.skip[task.pre[j]] = true; // 标记当前任务已跳过
        }
      }
      new_state.can_skip.erase(new_state.can_skip.begin() + (it - dp[i].can_skip.begin())); // 从可以完成的任务列表中移除当前任务

      if(task.is_video) {
        new_state.score += video_score; // 如果是视频任务，增加视频分数
        new_state.day += video_time + skip_num; // 增加观看视频的时间
      } else {
        new_state.score += work_score; // 如果是大作业，增加大作业分数
        new_state.day += work_time + skip_num; // 增加完成大作业的时间
      }

      update_can_do(new_state.can_do, new_state, task_id); // 更新可以完成的任务列表
      
      if(new_state.day > T) continue; // 如果超过期末前的剩余时间，则跳过该状态
      dp[new_state.day] = dp[new_state.day].score > new_state.score ? dp[new_state.day] : new_state; // 更新状态
    }
  }

  int max_score = dp[0].score + (30) * review_score; // 最大得分
  int max_id = 0; // 最大得分对应的天数
  for(int i = 0; i < 30; i++) {
    if (dp[i].score + (30 - i) * review_score <= max_score)
    {
      max_id = i; // 更新最大得分对应的天数
      max_score = dp[i].score + (30 - i) * review_score; // 更新最大得分
    }
  }
  cout <<"最多能拿"<<basis_score + max_score <<"分"<< endl; // 输出最大得分
  cout<<"剩下"<<30-max_id<<"天复习"<<endl;
  cout<<"作业完成情况为"<<endl;
  for(int i = 1; i <= w_n + v_n; i++) {
    if(i <= w_n) {
      if (dp[max_id].st[i])
      {
        cout << "大作业" << i << "已完成" << endl; // 输出已完成的任务
      }
      else
      {
        cout << "大作业" << i << "未完成" << endl; // 输出未完成的任务
      }
    } else {
      if (dp[max_id].st[i] && !dp[max_id].skip[i])
      {
        cout << "视频" << i << "已完成" << endl; // 输出已完成的任务
      }
      else
      {
        cout << "视频" << i  << "未完成" << endl; // 输出未完成的任务
      }
    }
  
  }
  
  return 0;
}




// 在完成一个任务之后（跳过也是完成），判断后面的节点能不能被放进can_do/can_skip
void update_can_do(vector<int>&can_do, state &s, int task_id){
  Node& task = nodes[task_id]; // 获取当前任务节点
  
  for(int i = 0;i<task.next.size();i++){
    
    int next_task = task.next[i]; // 获取后续任务编号
    
    if(s.st[next_task]) continue; // 如果后续任务已经完成，则跳过
    
    Node &next_node = nodes[next_task]; // 获取后续任务节点

    bool can_do_st[w_n + v_n + 1];
    for (int j = 0; j < can_do.size(); j++)
    {
      can_do_st[j] = 1;
    }
    
    bool can_to_skip = 1; // 是否可以跳过后续任务
    bool can_to_do = 1; // 是否可以完成后续任务
    
    for(int j = 0;j<next_node.pre.size();j++){
      int pre_task_id = next_node.pre[j]; // 获取前置任务编号
      if (!s.st[pre_task_id])
      {                           // 如果前置任务未完成
        can_to_do = 0; // 标记该后续任务不能被添加到can_do
        if(!can_do_st[pre_task_id]){ // 如果前置任务不在can_do中，也不在st中
          can_to_skip = 0; // 标记该后续任务不能被添加到can_skip
          break;           // 不能将后续任务添加到can_do或者 can_skip
        }
        
      }
    }
    
    //这里可能重复加，但是无所谓*****？
    
    if(can_to_do) { // 如果可以完成后续任务
      s.can_do.push_back(next_task); // 将后续任务添加到可以完成的任务列表
    }
    else if(can_to_skip) { // 如果可以跳过后续任务
      can_do_st[next_task] = 0; // 标记该后续任务不能被添加到can_do
      s.can_skip.push_back(next_task); // 将后续任务添加到可以跳过的任务列表
    }
  }
}