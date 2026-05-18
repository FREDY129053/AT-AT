import asyncio

from . import logger

from .run_agent import run_agent

async def amain():
    logger.info("AB TESTER START")
    await run_agent(7, trace=True, headless=True)


def main():
    asyncio.run(amain())


#############################
#######    METRICS    #######
#############################
# Главная метрика результата
# Доля успешных выполнений
#   success_rate = successful_runs / all_runs

# Метрики эффективности
# Число шагов до успеха
#   steps_to_success = step_no на момент успешного terminate

# Число действий на задачу
#   actions_per_task = count(all action logs)
#   actions_per_success = count(actions) / count(successful_runs)

# Эффективность траектории
#   trajectory_efficiency = success_flag / number_of_steps

# Метрики трения и ошибок
# Доля неудачных действий
#   invalid_action_rate = failed_actions / all_actions

# Доля действий, которые ничего не изменили
#   no_state_change_rate = actions where state_hash_after == state_hash_before / all_actions

# Доля возвратов и повторов
#   backtrack_rate = back_actions / all_actions
#   repeat_state_rate = revisits_to_same_state / all_states_visited

# Доля восстановлений после ошибки
#   recovery_rate = successful_runs_with_at_least_one_error / runs_with_at_least_one_error
#   recovery_after_error_steps = steps_between_first_error_and_success

# Доля прогонов, упершихся в лимит шагов
#   max_step_exhaustion_rate = runs_where_step_no == max_steps / all_runs

# Доля прерываний из-за краша / модалки / сети
#   page_crash_rate = runs_with_crash / all_runs
#   dialog_block_rate = runs_blocked_by_dialog / all_runs
#   network_failure_rate = runs_with_requestfailed_on_navigation / all_runs

# Метрики по персонам
# Эффект по сегментам персон
#   metric_B(segment) - metric_A(segment)