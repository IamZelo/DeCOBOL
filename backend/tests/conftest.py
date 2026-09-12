"""
Pytest configuration and shared fixtures for DeCOBOL test suite.
"""

import pytest
from app import create_app
from app.api.jobs import job_store


@pytest.fixture
def app():
    """Create a new Flask app instance for testing."""
    test_app = create_app({"TESTING": True, "FLASK_DEBUG": False})
    return test_app


@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_job_store():
    """Ensure a clean job store before each test."""
    with job_store._lock:
        job_store._jobs.clear()
    yield


@pytest.fixture
def sample_cobol_hello():
    return """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-GREETING PIC X(20).
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY 'HELLO WORLD'.
    """


@pytest.fixture
def sample_cobol_payroll():
    return """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-EMP-ID   PIC 9(5).
       01 WS-EMP-NAME PIC X(25).
       01 WS-SALARY   PIC S9(7)V99.
       PROCEDURE DIVISION.
       CALC-PAYROLL.
           DISPLAY 'PROCESSING PAYROLL'.
    """
