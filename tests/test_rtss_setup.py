import xml.etree.ElementTree as ET
from pathlib import Path

from ds2counter.rtss_setup import _task_xml

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_task_xml_runs_rtss_elevated_on_demand_without_limits():
    path = Path(r"C:\Program Files (x86)\Riva & Tuner\RTSS.exe")
    root = ET.fromstring(_task_xml(path).replace('encoding="UTF-16"', ""))
    assert root.find("t:Actions/t:Exec/t:Command", NS).text == str(path)
    assert root.find("t:Actions/t:Exec/t:WorkingDirectory", NS).text == str(path.parent)
    assert root.find("t:Principals/t:Principal/t:RunLevel", NS).text == "HighestAvailable"
    assert root.find("t:Principals/t:Principal/t:LogonType", NS).text == "InteractiveToken"
    assert root.find("t:Triggers", NS) is None  # tylko na żądanie licznika
    settings = root.find("t:Settings", NS)
    assert settings.find("t:ExecutionTimeLimit", NS).text == "PT0S"
    assert settings.find("t:DisallowStartIfOnBatteries", NS).text == "false"
