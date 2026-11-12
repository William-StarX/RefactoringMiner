import importlib
import pytest

@pytest.fixture
def package():
    return importlib.import_module("refactoringminer_agent")

@pytest.fixture
def module_name():
    return "refactoringminer_agent"
