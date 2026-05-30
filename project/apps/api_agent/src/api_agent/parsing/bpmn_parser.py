import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from lxml.etree import XMLParser, _Element, parse


class BPMNParser:
    _HTTP_HINT_RE = re.compile(
        r"\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/\S+)", re.IGNORECASE
    )
    _node_tags = [
        "startEvent",
        "task",
        "userTask",
        "serviceTask",
        "scriptTask",
        "exclusiveGateway",
        "parallelGateway",
        "inclusiveGateway",
        "callActivity",
        "subProcess",
        "endEvent",
    ]

    def __init__(self, filepath: str) -> None:
        self.bpmn_file = Path(filepath)

        if not self.bpmn_file.exists():
            raise FileNotFoundError(f"Файл '{filepath}' не найден")

    def __text_of(self, elem: Any) -> Optional[str]:
        if elem is None or len(elem) == 0:
            return None

        return "".join(elem.itertext()).strip() or None

    def parse_bpmn(self) -> Dict[str, Any]:
        parser = XMLParser(remove_comments=True)
        # TODO: ошибка при передаче НЕ файла
        root: _Element = parse(self.bpmn_file, parser).getroot()

        processes = []
        for proc in root.xpath('.//*[local-name()="process"]'):
            proc_id = proc.get("id")
            proc_obj = {
                "id": proc_id,
                "isExecutable": proc.get("isExecutable"),
                "nodes": [],
                "flows": [],
            }

            for tag in self._node_tags:
                for el in proc.xpath(".//*[local-name()=$name]", name=tag):
                    el_id = el.get("id")

                    el_name = el.get("name") or self.__text_of(
                        el.xpath('.//*[local-name()="documentation"]')
                    )

                    docs = None
                    docs_elem = el.xpath('.//*[local-name()="documentation"]')
                    if docs_elem is not None:
                        docs = self.__text_of(docs_elem)

                    ext = {}
                    ext_el = el.xpath('.//*[local-name()="extensionElements"]')
                    if ext_el is not None:
                        for child in ext_el:
                            ext.setdefault(child.tag, []).append(self.__text_of(child))

                    api_hint = None
                    if el_name:
                        matched = self._HTTP_HINT_RE.search(el_name)
                        if matched:
                            api_hint = {
                                "method": matched.group(1).upper(),
                                "path": matched.group(2),
                            }

                    node = {
                        "id": el_id,
                        "type": tag,
                        "name": el_name,
                        "documentation": docs,
                        "extension": ext or None,
                        "api_hint": api_hint,
                    }
                    proc_obj["nodes"].append(node)

            for sf in proc.xpath('.//*[local-name()="sequenceFlow"]'):
                sf_id = sf.get("id")

                source = sf.get("sourceRef")
                target = sf.get("targetRef")

                name = sf.get("name") or None

                cond = None
                cond_el = sf.xpath('.//*[local-name()="conditionExpression"]')
                if cond_el is not None:
                    cond = self.__text_of(cond_el)

                proc_obj["flows"].append(
                    {
                        "id": sf_id,
                        "sourceRef": source,
                        "targetRef": target,
                        "name": name,
                        "condition": cond,
                    }
                )

            processes.append(proc_obj)

        return {"processes": processes}
    
    def get_json_bpmn(self, *, indent: int | None = None):
        # WARN: 1 процесс идет только
        return json.dumps(self.parse_bpmn()['processes'][0], ensure_ascii=False, indent=indent)