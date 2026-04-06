"""
计划合理性检查模块：生成计划后的基础规则验证。
不涉及教育学科学性，仅检查时间、任务量等显性要素是否合理。
"""


class PlanValidator:
    """计划生成后的合理性检查"""

    def __init__(self, strict_mode=False):
        """
        strict_mode=True: 严格模式，不合理的计划直接返回错误
        strict_mode=False: 宽松模式，返回警告但允许使用
        """
        self.strict_mode = strict_mode
        self.warnings = []
        self.errors = []

    def validate(self, parsed_goal: dict, plan_data: dict) -> dict:
        """
        完整的计划验证。
        返回: {
            "is_valid": bool,  # 是否通过所有检查
            "warnings": [],    # 警告列表
            "errors": [],      # 错误列表（严格模式下会导致失败）
            "suggestions": []  # 改进建议
        }
        """
        self.warnings = []
        self.errors = []
        suggestions = []

        # 1. 检查时间安排合理性
        time_check = self._check_time_reasonability(parsed_goal, plan_data)
        self.warnings.extend(time_check.get("warnings", []))
        self.errors.extend(time_check.get("errors", []))
        suggestions.extend(time_check.get("suggestions", []))

        # 2. 检查任务分布均衡性
        task_check = self._check_task_balance(plan_data)
        self.warnings.extend(task_check.get("warnings", []))
        self.errors.extend(task_check.get("errors", []))
        suggestions.extend(task_check.get("suggestions", []))

        # 3. 检查里程碑合理性
        milestone_check = self._check_milestones(plan_data)
        self.warnings.extend(milestone_check.get("warnings", []))
        self.errors.extend(milestone_check.get("errors", []))
        suggestions.extend(milestone_check.get("suggestions", []))

        # 4. 检查阶段划分合理性
        stage_check = self._check_stages(plan_data)
        self.warnings.extend(stage_check.get("warnings", []))
        self.errors.extend(stage_check.get("errors", []))
        suggestions.extend(stage_check.get("suggestions", []))

        # 综合判断
        is_valid = len(self.errors) == 0 or not self.strict_mode

        return {
            "is_valid": is_valid,
            "warnings": self.warnings,
            "errors": self.errors,
            "suggestions": suggestions,
            "summary": self._generate_summary(is_valid)
        }

    def _check_time_reasonability(self, parsed_goal: dict, plan_data: dict) -> dict:
        """检查时间安排是否均衡"""
        warnings = []
        errors = []
        suggestions = []

        duration_days = parsed_goal.get("duration_days", 0)
        daily_hours = parsed_goal.get("daily_hours", 0)
        daily_tasks = plan_data.get("daily_tasks", [])

        if not duration_days or not daily_hours or not daily_tasks:
            return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

        total_planned_hours = sum(t.get("estimated_hours", 0) for t in daily_tasks)
        expected_total_hours = duration_days * daily_hours

        # 检查 1：总时长差异
        if total_planned_hours == 0:
            errors.append("❌ 计划中无任何任务时长信息")
        else:
            ratio = total_planned_hours / expected_total_hours if expected_total_hours > 0 else 0
            if ratio < 0.7:
                warnings.append(
                    f"⚠️ 任务总时长({total_planned_hours}h) 远低于预期({expected_total_hours}h)，"
                    f"学习可能不够充实"
                )
                suggestions.append(f"增加任务时长至至少 {int(expected_total_hours * 0.8)} 小时")
            elif ratio > 1.3:
                errors.append(
                    f"❌ 任务总时长({total_planned_hours}h) 远超预期({expected_total_hours}h)，"
                    f"执行难度过高"
                )
                suggestions.append(f"减少任务或延长学习周期")

        # 检查 2：每日时长均衡性
        daily_hours_list = [t.get("estimated_hours", 0) for t in daily_tasks]
        if daily_hours_list:
            max_daily = max(daily_hours_list)
            min_daily = min(daily_hours_list)
            if max_daily > 0 and min_daily > 0:
                variance = max_daily / min_daily
                if variance > 3:
                    warnings.append(
                        f"⚠️ 每日任务时长差异较大（最高{max_daily}h，最低{min_daily}h），"
                        f"学习节奏不稳定"
                    )
                    suggestions.append("调整每日任务时长，使其相对均衡（推荐方差 < 2）")

        return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

    def _check_task_balance(self, plan_data: dict) -> dict:
        """检查每日任务分布是否均衡"""
        warnings = []
        errors = []
        suggestions = []

        daily_tasks = plan_data.get("daily_tasks", [])
        if not daily_tasks:
            return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

        # 检查每日任务数量
        task_counts = {}
        for task in daily_tasks:
            day = task.get("day", 0)
            task_counts[day] = task_counts.get(day, 0) + 1

        # 计算任务数分布
        counts = list(task_counts.values())
        if counts:
            max_count = max(counts)
            min_count = min(counts)

            if max_count > 8:
                errors.append(
                    f"❌ 单日任务数最多达 {max_count} 个，任务堆积风险高"
                )
                suggestions.append("将超过 8 个的任务分散到其他日期")

            if max_count > 0 and min_count > 0 and max_count > min_count * 2.5:
                warnings.append(
                    f"⚠️ 任务分布不均（最多日 {max_count} 个，最少日 {min_count} 个），"
                    f"学习强度差异大"
                )
                suggestions.append("重新分配任务，使日均任务数相对均匀")

        return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

    def _check_milestones(self, plan_data: dict) -> dict:
        """检查里程碑的合理性和分布"""
        warnings = []
        errors = []
        suggestions = []

        milestones = plan_data.get("milestones", [])
        daily_tasks = plan_data.get("daily_tasks", [])

        if not milestones:
            warnings.append("⚠️ 计划中未设置里程碑，进度追踪可能不够清晰")
            suggestions.append("为关键节点添加里程碑（通常 3-5 个为宜）")
            return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

        # 检查里程碑数量
        if len(milestones) > 10:
            warnings.append(
                f"⚠️ 里程碑过多（{len(milestones)} 个），可能分散注意力"
            )
            suggestions.append("合并相关里程碑，保持在 3-5 个关键里程碑")

        if len(milestones) == 1:
            warnings.append("⚠️ 仅有 1 个里程碑，过程跟进不足")
            suggestions.append("增加中间里程碑以跟进学习进度")

        return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

    def _check_stages(self, plan_data: dict) -> dict:
        """检查阶段划分是否合理"""
        warnings = []
        errors = []
        suggestions = []

        stages = plan_data.get("stages", [])
        daily_tasks = plan_data.get("daily_tasks", [])

        if not stages:
            errors.append("❌ 计划未划分阶段，学习结构不清晰")
            suggestions.append("根据学习内容划分 2-4 个阶段（如：基础、进阶、实践、总结）")
            return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

        # 检查阶段数量
        if len(stages) > 6:
            warnings.append(
                f"⚠️ 阶段数过多（{len(stages)} 个），易造成碎片化"
            )
            suggestions.append("合并相关阶段，保持在 2-4 个主要阶段")

        if len(stages) == 1:
            warnings.append("⚠️ 仅有 1 个阶段，学习路径结构不够清晰")
            suggestions.append("至少划分为 2 个阶段（如初阶和进阶）")

        return {"warnings": warnings, "errors": errors, "suggestions": suggestions}

    def _generate_summary(self, is_valid: bool) -> str:
        """生成验证摘要"""
        if is_valid and not self.warnings:
            return "✅ 计划结构完全合理，可直接执行"
        elif is_valid:
            return f"⚠️ 计划基本合理（有 {len(self.warnings)} 个警告），建议参考建议优化后再执行"
        else:
            return f"❌ 计划存在 {len(self.errors)} 个问题，需要修改后再执行"
