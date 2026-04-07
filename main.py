import os

from services.study_planner_service import StudyPlannerService


API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


if __name__ == "__main__":
    service = StudyPlannerService(API_KEY)
    user_input = "我想两周复习操作系统，每天3小时，主要看进程和内存管理"

    # 1 生成计划并落库
    plan, plan_rag = service.create_plan(user_input)
    if not plan:
        print("计划生成失败")
        raise SystemExit(1)
    print("学习计划：")
    print(plan["plan_data"])
    print("\nRAG 片段预览：")
    print((plan_rag or "(无)")[:500])

    # 2 记录进度
    progress = service.record_progress(
        plan["id"],
        {
            "completion_ratio": 55,
            "completed_tasks": "完成进程调度",
            "pending_tasks": "内存管理未完成",
            "delay_reason": "时间不足",
            "note": "需要加强页面置换算法",
        },
    )
    print("\n学习反馈：")
    print(progress["feedback"])

    # 3 动态调整
    adjusted = service.adjust_plan(plan["id"])
    print("\n优化建议：")
    print(adjusted["adjustment"] if adjusted else "暂无可调整内容")