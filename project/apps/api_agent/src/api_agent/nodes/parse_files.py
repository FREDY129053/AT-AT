from api_agent.schemas import ApiTesterState
from api_agent.services.parser import BPMNParser

def parse_files_node(state: ApiTesterState) -> dict:
    # TODO: типы файлов в match..case и в результате парсинга тоже сохранить тип для промптов
    # processes = []
    # for file in state.files:
    #     processes.append(BPMNParser(file).get_json_bpmn())
    processes = BPMNParser(state.files).get_json_bpmn()

    return {"processes": processes}