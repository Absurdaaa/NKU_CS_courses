import time
import random
from enum import Enum

class PackageState(Enum):
    zero2one = 0    # 入库
    one2two = 1     # 分配
    two2three = 2   # 分拣
    three2four = 3  # 包装 (新增阶段)
    four2five = 4   # 质检 (原three2four)
    five2six = 5    # 出库 (原four2five)

class Package:
    def __init__(self, pid):
        self.id = pid
        self.state = PackageState.zero2one
        self.retry_count = 0
        self.finished = False
        self.enter_cycle = None
        self.exit_cycle = None
        self.special_packaging = False
        self.packaging = None  # 包装类型，None表示未包装，True表示特殊包装，False表示普通包装

    def __repr__(self):
        return f"Pkg{self.id}"

class Pipeline:
    def __init__(self):
        self.stages = [None] * 6          # 现在有6个阶段
        self.input_buffers = [None] * 6   # 候补区也扩展到6个
        self.pending = []
        self.completed = []
        self.cycle = 0
        self.refund_probability = 0.05
        self.refund_threshold = 0.2
        self.refund_count = 0
        # 包装预测位，0的时候预测普通包装，1的时候预测特殊包装
        self.prodict = 0
        # 添加阶段使用计数器
        self.stage_use_count = 0

    def insert_package(self, package):
        self.pending.append(package)

    def clock_cycle(self):
        print(f"\n===== 周期 {self.cycle} =====")

        # 出库阶段完成处理 (阶段5)
        if self.stages[5]:
            self.stages[5].exit_cycle = self.cycle
            print(f"{self.stages[5]} 出库完成")
            self.stages[5].finished = True
            self.completed.append(self.stages[5])
            self.stages[5] = None

        # 候补包裹优先插入流水线
        for i in range(6):
            if self.stages[i] is None and self.input_buffers[i]:
                print(f"{self.input_buffers[i]} 从候补区进入 {PackageState(i).name}")
                self.stages[i] = self.input_buffers[i]
                self.input_buffers[i] = None
        
        # 包装阶段逻辑 (阶段3)
        if self.stages[3]:
            pkg = self.stages[3]
            # 根据预测位进行包装
            if self.prodict == 0:
                pkg.packaging = False  # 普通包装
                print(f"{pkg} 使用普通包装")
            else:
                pkg.packaging = True   # 特殊包装
                print(f"{pkg} 使用特殊包装")

        # 质检逻辑 (阶段4)
        if self.stages[4]:
            pkg = self.stages[4]
            
            # 检查包装是否正确
            packaging_wrong = pkg.packaging != pkg.special_packaging
            
            if packaging_wrong:
                print(f"{pkg} 包装错误，需要重新包装")
                # 翻转预测位，下次用另一种包装
                self.prodict = 1 - self.prodict
                print(f"预测位更新为: {'特殊包装' if self.prodict == 1 else '普通包装'}")
                
                # 退回包装阶段 (阶段3)
                if self.stages[3] is None:
                    self.stages[3] = pkg
                    self.stages[4] = None
                    # 重置包裹的包装状态，允许重新包装
                    pkg.packaging = None
                elif self.input_buffers[3] is None:
                    self.input_buffers[3] = pkg
                    self.stages[4] = None
                    # 重置包裹的包装状态
                    pkg.packaging = None
                    print(f"{pkg} 想退回包装阶段但被阻塞，暂存候补区")
                else:
                    print(f"{pkg} 想退回包装阶段但候补也满，留在质检区")
            else:
                print(f"{pkg} 包装正确，继续质检流程")
                # ... 保留原有的质检逻辑 ...

        # 推进逻辑
        for i in reversed(range(1, 6)):
            if self.stages[i] is not None or self.input_buffers[i] is not None:
                continue

            if self.stages[i - 1]:
                self.stages[i] = self.stages[i - 1]
                self.stages[i - 1] = None
                self.stages[i].state = PackageState(i)
                print(f"{self.stages[i]} 从阶段{i-1}推进到阶段{i}")

        # 插入新的包裹（入库）
        if self.stages[0] is None and self.pending:
            new_pkg = self.pending.pop(0)
            print(f"{new_pkg} 进入入库阶段")
            self.stages[0] = new_pkg
            new_pkg.enter_cycle = self.cycle

        # 打印状态
        for i, stage in enumerate(self.stages):
            print(f"阶段 {PackageState(i).name}: {stage}")
        print("候补区状态:")
        for i, buf in enumerate(self.input_buffers):
            if buf:
                print(f"  {PackageState(i).name} 候补包裹: {buf}")
        
        # 统计当前周期中使用的阶段数
        active_stages = sum(1 for stage in self.stages if stage)
        self.stage_use_count += active_stages
        self.cycle += 1

    def refund(self):
        if random.random() < self.refund_probability:
            if self.pending:
                refunded_pkg = self.pending.pop(random.randint(0, len(self.pending) - 1))
                self.refund_count += 1
                print(f"{refunded_pkg} 从待处理队列中退货")

            for i in range(len(self.stages)):
                if self.stages[i] and random.random() < self.refund_probability:
                    refunded_pkg = self.stages[i]
                    self.stages[i] = None
                    print(f"{refunded_pkg} 从阶段 {PackageState(i).name} 退货")
                    self.refund_count += 1

    def run(self, cycles=50):
        for _ in range(cycles):
            self.refund()
            self.clock_cycle()
            # time.sleep(0.5)

        print("\n=== 运行结束 ===")
        print(f"完成包裹数: {len(self.completed)}")
        print(f"已完成包裹ID: {[p.id for p in self.completed]}")
        print(f"未完成包裹: {[p.id for p in self.pending]}")
        print(f"流水线中包裹: {[s.id for s in self.stages if s]}")
        print(f"候补区包裹: {[b.id for b in self.input_buffers if b]}")
        
def evaluate(pipeline: Pipeline):
    print("\n=== 性能评估 ===")
    total_cycles = pipeline.cycle
    total_completed = len(pipeline.completed)
    total_refunds = pipeline.refund_count

    throughput = total_completed / total_cycles if total_cycles else 0

    latencies = [
        pkg.exit_cycle - pkg.enter_cycle
        for pkg in pipeline.completed
        if pkg.enter_cycle is not None and pkg.exit_cycle is not None
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    total_stage_uses = sum(1 for cycle in range(total_cycles) for stage in pipeline.stages if stage)
    # 使用累计的阶段使用次数计算利用率
    utilization = pipeline.stage_use_count / (6 * total_cycles) if total_cycles else 0
    

    print(f"总周期数: {total_cycles}")
    print(f"完成包裹数: {total_completed}")
    print(f"退货包裹数: {total_refunds}")
    print(f"吞吐率: {throughput:.4f} 包裹/周期")
    print(f"平均延迟: {avg_latency:.2f} 周期/包裹")
    print(f"流水线平均利用率: {utilization:.2%}")

def main():
    pipeline = Pipeline()
    consecutive_special = 0
    for i in range(1, 100000):
      if consecutive_special > 0 or random.random() < 0.3:
        pkg = Package(i)
        pkg.special_packaging = True
        pipeline.insert_package(pkg)
        consecutive_special = max(0, consecutive_special - 1)  # 确保不会小于0
        if consecutive_special == 0:
          consecutive_special = random.randint(5, 10)  # 连续生成1到10个特殊包装订单
      else:
        pipeline.insert_package(Package(i))

    pipeline.run(100000)
    evaluate(pipeline)

if __name__ == "__main__":
    main()