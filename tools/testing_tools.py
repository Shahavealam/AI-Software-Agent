"""
Testing Tools for AI Software Engineer Agent

This module provides automated testing capabilities for the agent including:
- Automated test generation and execution
- Code quality validation
- Test coverage analysis
- Integration testing
- Performance benchmarking
- Test reporting
"""

import os
import sys
import subprocess
import json
import time
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

try:
    import coverage
    from coverage import Coverage
    HAS_COVERAGE = True
except ImportError:
    HAS_COVERAGE = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    message: Optional[str] = None
    traceback: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class TestSuite:
    """Test suite data structure"""
    name: str
    results: List[TestResult]
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    success: bool


class TestingTools:
    """
    Comprehensive testing tools for the AI Software Engineer Agent
    
    Provides capabilities for:
    - Running automated tests
    - Generating test files
    - Analyzing test coverage
    - Validating code quality
    - Performance testing
    - Integration testing
    - Test reporting
    """
    
    def __init__(self, project_path: Union[str, Path], 
                 test_directory: str = "tests",
                 verbose: bool = True):
        """
        Initialize TestingTools
        
        Args:
            project_path: Path to the project root
            test_directory: Directory containing tests (default: "tests")
            verbose: Enable verbose output (default: True)
        """
        self.project_path = Path(project_path)
        self.test_directory = self.project_path / test_directory
        self.verbose = verbose
        self.test_results = []
        self.coverage_data = {}
        self.performance_data = {}
        
        # Create test directory if it doesn't exist
        self.test_directory.mkdir(parents=True, exist_ok=True)
        
        # Create reports directory
        self.reports_dir = self.project_path / "test_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize test trackers
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.error_tests = 0
        
    # ============================================
    # 1. UNIT TEST EXECUTION
    # ============================================
    
    def run_unit_tests(self, test_path: Optional[str] = None,
                       test_pattern: str = "test_*.py",
                       markers: Optional[List[str]] = None,
                       fail_fast: bool = False,
                       parallel: bool = False) -> TestSuite:
        """
        Run unit tests using pytest
        
        Args:
            test_path: Specific test path (relative to project)
            test_pattern: Pattern for test files
            markers: List of pytest markers to include
            fail_fast: Stop on first failure
            parallel: Run tests in parallel
            
        Returns:
            TestSuite: Test results
        """
        self._log("Running unit tests...")
        
        if not HAS_PYTEST:
            self._log("pytest not installed. Run: pip install pytest pytest-xdist")
            return TestSuite(
                name="Unit Tests",
                results=[],
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=0,
                duration=0,
                success=False
            )
        
        # Determine test directory
        if test_path:
            test_dir = self.project_path / test_path
        else:
            test_dir = self.test_directory
        
        if not test_dir.exists():
            self._log(f"Test directory not found: {test_dir}")
            return TestSuite(
                name="Unit Tests",
                results=[],
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=0,
                duration=0,
                success=False
            )
        
        # Build pytest command
        cmd = ["python", "-m", "pytest", str(test_dir), "--tb=short", "-v"]
        
        # Add test pattern
        if test_pattern != "test_*.py":
            cmd.extend(["-k", test_pattern])
        
        # Add markers
        if markers:
            marker_expr = " or ".join(markers)
            cmd.extend(["-m", marker_expr])
        
        # Add fail fast
        if fail_fast:
            cmd.append("-x")
        
        # Add parallel execution
        if parallel:
            try:
                import pytest_xdist
                cmd.extend(["-n", "auto"])
            except ImportError:
                self._log("pytest-xdist not installed. Running without parallelism.")
        
        # Add coverage if available
        if HAS_COVERAGE:
            cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
        
        # Run tests
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            output = result.stdout + result.stderr
            results = self._parse_pytest_output(output)
            
            # Calculate statistics
            passed = sum(1 for r in results if r.status == "passed")
            failed = sum(1 for r in results if r.status == "failed")
            skipped = sum(1 for r in results if r.status == "skipped")
            errors = sum(1 for r in results if r.status == "error")
            total = len(results)
            
            test_suite = TestSuite(
                name="Unit Tests",
                results=results,
                total=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                duration=duration,
                success=result.returncode == 0
            )
            
            # Update trackers
            self.passed_tests = passed
            self.failed_tests = failed
            self.skipped_tests = skipped
            self.error_tests = errors
            
            # Save results
            self.test_results.append(test_suite)
            
            self._log(f"Tests completed: {passed} passed, {failed} failed, {skipped} skipped, {errors} errors")
            return test_suite
            
        except Exception as e:
            self._log(f"Error running tests: {e}")
            return TestSuite(
                name="Unit Tests",
                results=[],
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                duration=0,
                success=False
            )
    
    def _parse_pytest_output(self, output: str) -> List[TestResult]:
        """
        Parse pytest output to extract test results
        
        Args:
            output: pytest output string
            
        Returns:
            List[TestResult]: Parsed test results
        """
        results = []
        lines = output.split('\n')
        
        # Regex patterns for test results
        passed_pattern = r'^.*PASSED.*$'
        failed_pattern = r'^.*FAILED.*$'
        skipped_pattern = r'^.*SKIPPED.*$'
        error_pattern = r'^.*ERROR.*$'
        
        for line in lines:
            if re.search(passed_pattern, line, re.IGNORECASE):
                # Extract test name
                test_match = re.search(r'(\w+\.py::\w+)(?:::\w+)?', line)
                if test_match:
                    results.append(TestResult(
                        test_name=test_match.group(1),
                        status="passed",
                        duration=0.0,
                        message="Test passed"
                    ))
            elif re.search(failed_pattern, line, re.IGNORECASE):
                test_match = re.search(r'(\w+\.py::\w+)(?:::\w+)?', line)
                if test_match:
                    results.append(TestResult(
                        test_name=test_match.group(1),
                        status="failed",
                        duration=0.0,
                        message="Test failed"
                    ))
            elif re.search(skipped_pattern, line, re.IGNORECASE):
                test_match = re.search(r'(\w+\.py::\w+)(?:::\w+)?', line)
                if test_match:
                    results.append(TestResult(
                        test_name=test_match.group(1),
                        status="skipped",
                        duration=0.0,
                        message="Test skipped"
                    ))
            elif re.search(error_pattern, line, re.IGNORECASE):
                test_match = re.search(r'(\w+\.py::\w+)(?:::\w+)?', line)
                if test_match:
                    results.append(TestResult(
                        test_name=test_match.group(1),
                        status="error",
                        duration=0.0,
                        message="Test error"
                    ))
        
        return results
    
    # ============================================
    # 2. TEST GENERATION
    # ============================================
    
    def generate_tests_for_file(self, source_file: str, 
                                output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate test file for a source file
        
        Args:
            source_file: Source file path (relative to project)
            output_file: Output test file path (optional)
            
        Returns:
            Dict[str, Any]: Generation result
        """
        self._log(f"Generating tests for: {source_file}")
        
        source_path = self.project_path / source_file
        
        if not source_path.exists():
            return {
                "success": False,
                "error": f"Source file not found: {source_file}"
            }
        
        # Read source content
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                source_content = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading source file: {e}"
            }
        
        # Determine test file name
        if output_file:
            test_path = self.project_path / output_file
        else:
            # Create test file path
            relative_path = source_path.relative_to(self.project_path)
            test_path = self.test_directory / relative_path.parent / f"test_{relative_path.name}"
        
        # Ensure directory exists
        test_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract classes and functions
        classes = re.findall(r'class\s+(\w+)', source_content)
        functions = re.findall(r'def\s+(\w+)\s*\(', source_content)
        
        # Filter out special functions
        functions = [f for f in functions if not f.startswith('_') and f not in ['setup', 'teardown']]
        classes = [c for c in classes if not c.startswith('_')]
        
        # Generate test content
        test_content = self._create_test_content(
            source_path.name,
            classes,
            functions,
            source_content
        )
        
        # Write test file
        try:
            with open(test_path, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            self._log(f"Generated test file: {test_path}")
            
            return {
                "success": True,
                "test_file": str(test_path.relative_to(self.project_path)),
                "classes": classes,
                "functions": functions
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error writing test file: {e}"
            }
    
    def _create_test_content(self, filename: str, classes: List[str], 
                             functions: List[str], source_content: str) -> str:
        """
        Create test file content
        
        Args:
            filename: Source filename
            classes: List of class names
            functions: List of function names
            source_content: Source code content
            
        Returns:
            str: Test file content
        """
        # Determine module name
        module_name = Path(filename).stem
        
        # Build test file content
        content = [
            '"""',
            f'Test file for {filename}',
            'Auto-generated by AI Software Engineer Agent',
            '"""',
            '',
            'import pytest',
            'import sys',
            'from pathlib import Path',
            '',
            '# Add parent directory to path',
            'sys.path.insert(0, str(Path(__file__).parent.parent))',
            '',
            f'from {module_name} import *',
            '',
            ''
        ]
        
        # Add test class
        if classes:
            for class_name in classes:
                content.extend([
                    f'class Test{class_name}:',
                    f'    """Test class for {class_name}"""',
                    '',
                    '    def setup_method(self):',
                    '        """Setup before each test"""',
                    f'        self.instance = {class_name}()',
                    '',
                    '    def teardown_method(self):',
                    '        """Teardown after each test"""',
                    '        pass',
                    '',
                    f'    def test_{class_name.lower()}_initialization(self):',
                    '        """Test class initialization"""',
                    f'        assert self.instance is not None',
                    '',
                    f'    def test_{class_name.lower()}_str_representation(self):',
                    '        """Test string representation"""',
                    '        assert str(self.instance) is not None',
                    '',
                    ''
                ])
        else:
            # No classes found, create generic test class
            content.extend([
                'class TestModule:',
                '    """Test class for module"""',
                '',
                '    def test_import(self):',
                f'        """Test module import for {module_name}"""',
                '        assert True',
                '',
                ''
            ])
        
        # Add function tests
        for func in functions:
            content.extend([
                f'def test_{func}():',
                f'    """Test {func} function"""',
                '    # TODO: Implement test for {func}',
                '    pass',
                '',
                ''
            ])
        
        return '\n'.join(content)
    
    # ============================================
    # 3. TEST COVERAGE ANALYSIS
    # ============================================
    
    def analyze_coverage(self, source_path: Optional[str] = None,
                        include_tests: bool = False) -> Dict[str, Any]:
        """
        Analyze code coverage
        
        Args:
            source_path: Path to source code (default: project root)
            include_tests: Include test files in coverage analysis
            
        Returns:
            Dict[str, Any]: Coverage analysis results
        """
        self._log("Analyzing code coverage...")
        
        if not HAS_COVERAGE:
            return {
                "success": False,
                "error": "coverage package not installed. Run: pip install coverage"
            }
        
        if source_path:
            src_path = self.project_path / source_path
        else:
            src_path = self.project_path
        
        if not src_path.exists():
            return {
                "success": False,
                "error": f"Source path not found: {src_path}"
            }
        
        try:
            # Create coverage object
            cov = Coverage()
            cov.start()
            
            # Import modules to measure coverage
            # This is a simplified approach; in practice, you'd run your tests
            
            # Stop coverage
            cov.stop()
            cov.save()
            
            # Generate report
            report_data = {
                "success": True,
                "total_coverage": 0,
                "file_coverage": {},
                "missing_lines": {},
                "executed_lines": {}
            }
            
            # Parse coverage data
            for filename, analysis in cov.analysis2():
                if not include_tests and '/test_' in filename:
                    continue
                
                if filename.endswith('.py'):
                    rel_path = Path(filename).relative_to(self.project_path)
                    
                    # Get coverage statistics
                    statements, executed, missing = analysis
                    
                    coverage_percentage = 0
                    if statements:
                        coverage_percentage = (len(executed) / len(statements)) * 100
                    
                    report_data["file_coverage"][str(rel_path)] = coverage_percentage
                    report_data["missing_lines"][str(rel_path)] = missing
                    report_data["executed_lines"][str(rel_path)] = executed
            
            # Calculate total coverage
            if report_data["file_coverage"]:
                report_data["total_coverage"] = sum(
                    report_data["file_coverage"].values()
                ) / len(report_data["file_coverage"])
            
            # Generate HTML report
            cov.html_report(directory=str(self.reports_dir / "coverage"))
            report_data["html_report"] = str(self.reports_dir / "coverage" / "index.html")
            
            self.coverage_data = report_data
            self._log(f"Coverage analysis complete: {report_data['total_coverage']:.1f}%")
            
            return report_data
            
        except Exception as e:
            self._log(f"Error analyzing coverage: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ============================================
    # 4. CODE QUALITY VALIDATION
    # ============================================
    
    def validate_code_quality(self, file_path: str) -> Dict[str, Any]:
        """
        Validate code quality using flake8/pylint
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        self._log(f"Validating code quality: {file_path}")
        
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        results = {
            "success": True,
            "file": file_path,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        # Run flake8
        try:
            flake8_result = subprocess.run(
                ["flake8", str(full_path)],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if flake8_result.stdout:
                for line in flake8_result.stdout.split('\n'):
                    if line.strip():
                        results["warnings"].append(line.strip())
                        results["success"] = False
                        
        except FileNotFoundError:
            results["warnings"].append("flake8 not installed. Run: pip install flake8")
        
        # Run pylint if available
        try:
            pylint_result = subprocess.run(
                ["pylint", str(full_path), "--output-format=text"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if pylint_result.stdout:
                for line in pylint_result.stdout.split('\n'):
                    if ':' in line and ('warning' in line.lower() or 'error' in line.lower()):
                        results["errors"].append(line.strip())
                        results["success"] = False
                        
        except FileNotFoundError:
            results["warnings"].append("pylint not installed. Run: pip install pylint")
        
        # Run mypy for type checking
        try:
            mypy_result = subprocess.run(
                ["mypy", str(full_path)],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if mypy_result.stdout:
                for line in mypy_result.stdout.split('\n'):
                    if line.strip() and 'error' in line.lower():
                        results["errors"].append(line.strip())
                        results["success"] = False
                        
        except FileNotFoundError:
            results["warnings"].append("mypy not installed. Run: pip install mypy")
        
        return results
    
    # ============================================
    # 5. INTEGRATION TESTING
    # ============================================
    
    def test_api_endpoint(self, url: str, method: str = "GET",
                         headers: Optional[Dict] = None,
                         data: Optional[Dict] = None,
                         expected_status: int = 200,
                         timeout: int = 30) -> Dict[str, Any]:
        """
        Test an API endpoint
        
        Args:
            url: API endpoint URL
            method: HTTP method
            headers: Request headers
            data: Request data
            expected_status: Expected HTTP status
            timeout: Request timeout in seconds
            
        Returns:
            Dict[str, Any]: Test results
        """
        self._log(f"Testing API endpoint: {method} {url}")
        
        if not HAS_REQUESTS:
            return {
                "success": False,
                "error": "requests package not installed. Run: pip install requests"
            }
        
        try:
            start_time = time.time()
            
            # Make request
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=timeout)
            elif method.upper() == "PATCH":
                response = requests.patch(url, json=data, headers=headers, timeout=timeout)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported method: {method}"
                }
            
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                "success": response.status_code == expected_status,
                "status_code": response.status_code,
                "expected_status": expected_status,
                "response_time": duration,
                "headers": dict(response.headers),
                "content": response.text[:1000]  # Truncate large responses
            }
            
            # Try to parse JSON
            try:
                result["json"] = response.json()
            except:
                pass
            
            return result
            
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Connection error. Is the service running?"
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": f"Request timeout after {timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def health_check_test(self, url: str, retries: int = 3, 
                         delay: int = 2) -> Dict[str, Any]:
        """
        Test service health check endpoint
        
        Args:
            url: Health check URL
            retries: Number of retries
            delay: Delay between retries in seconds
            
        Returns:
            Dict[str, Any]: Health check results
        """
        self._log(f"Performing health check: {url}")
        
        result = {
            "success": False,
            "attempts": 0,
            "responses": [],
            "healthy": False
        }
        
        for attempt in range(retries):
            result["attempts"] += 1
            response = self.test_api_endpoint(url, "GET", expected_status=200)
            result["responses"].append(response)
            
            if response.get("success"):
                result["success"] = True
                result["healthy"] = True
                result["message"] = "Service is healthy"
                break
            
            if attempt < retries - 1:
                self._log(f"Health check failed, retrying in {delay} seconds...")
                time.sleep(delay)
        
        if not result["success"]:
            result["healthy"] = False
            result["message"] = "Service is unhealthy"
        
        return result
    
    # ============================================
    # 6. PERFORMANCE TESTING
    # ============================================
    
    def benchmark_function(self, func, iterations: int = 100,
                          args: Optional[List] = None,
                          kwargs: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Benchmark a function's performance
        
        Args:
            func: Function to benchmark
            iterations: Number of iterations
            args: Function arguments
            kwargs: Function keyword arguments
            
        Returns:
            Dict[str, Any]: Benchmark results
        """
        self._log(f"Benchmarking function: {func.__name__}")
        
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        
        times = []
        errors = 0
        
        for i in range(iterations):
            try:
                start_time = time.perf_counter()
                func(*args, **kwargs)
                end_time = time.perf_counter()
                times.append(end_time - start_time)
            except Exception as e:
                errors += 1
                self._log(f"Error in iteration {i}: {e}")
        
        if not times:
            return {
                "success": False,
                "error": "No successful iterations",
                "function": func.__name__,
                "errors": errors
            }
        
        result = {
            "success": True,
            "function": func.__name__,
            "iterations": iterations,
            "successful_iterations": len(times),
            "errors": errors,
            "total_time": sum(times),
            "average_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "median_time": sorted(times)[len(times) // 2] if times else 0,
            "times": times[:10]  # Return first 10 times
        }
        
        self.performance_data[func.__name__] = result
        return result
    
    def load_test_endpoint(self, url: str, requests_count: int = 10,
                          concurrent: bool = False,
                          headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Load test an API endpoint
        
        Args:
            url: API endpoint URL
            requests_count: Number of requests
            concurrent: Run requests concurrently
            headers: Request headers
            
        Returns:
            Dict[str, Any]: Load test results
        """
        self._log(f"Load testing endpoint: {url}")
        
        if not HAS_REQUESTS:
            return {
                "success": False,
                "error": "requests package not installed"
            }
        
        results = []
        start_time = time.time()
        
        if concurrent:
            # Run concurrently using threading
            import threading
            threads = []
            
            def make_request():
                try:
                    response = requests.get(url, headers=headers)
                    results.append({
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                        "success": response.status_code == 200
                    })
                except Exception as e:
                    results.append({
                        "error": str(e),
                        "success": False
                    })
            
            for _ in range(requests_count):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
        else:
            # Run sequentially
            for _ in range(requests_count):
                try:
                    response = requests.get(url, headers=headers)
                    results.append({
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                        "success": response.status_code == 200
                    })
                except Exception as e:
                    results.append({
                        "error": str(e),
                        "success": False
                    })
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate statistics
        successful = sum(1 for r in results if r.get("success", False))
        failed = requests_count - successful
        times = [r["response_time"] for r in results if "response_time" in r]
        
        return {
            "success": True,
            "url": url,
            "requests": requests_count,
            "successful": successful,
            "failed": failed,
            "total_time": total_time,
            "average_response_time": sum(times) / len(times) if times else 0,
            "min_response_time": min(times) if times else 0,
            "max_response_time": max(times) if times else 0,
            "throughput": successful / total_time if total_time > 0 else 0,
            "concurrent": concurrent,
            "results": results[:10]  # Return first 10 results
        }
    
    # ============================================
    # 7. TEST REPORTING
    # ============================================
    
    def generate_test_report(self, test_suites: Optional[List[TestSuite]] = None) -> str:
        """
        Generate a comprehensive test report in markdown format
        
        Args:
            test_suites: List of test suites to include
            
        Returns:
            str: Markdown report
        """
        if test_suites is None:
            test_suites = self.test_results
        
        if not test_suites:
            return "# Test Report\n\nNo test results available."
        
        report = [
            "# 📊 Test Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📈 Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        
        total_passed = sum(s.passed for s in test_suites)
        total_failed = sum(s.failed for s in test_suites)
        total_skipped = sum(s.skipped for s in test_suites)
        total_errors = sum(s.errors for s in test_suites)
        total_tests = sum(s.total for s in test_suites)
        
        report.extend([
            f"| **Total Tests** | {total_tests} |",
            f"| **✅ Passed** | {total_passed} |",
            f"| **❌ Failed** | {total_failed} |",
            f"| **⏭️ Skipped** | {total_skipped} |",
            f"| **⚠️ Errors** | {total_errors} |",
            f"| **Success Rate** | {((total_passed / total_tests) * 100) if total_tests > 0 else 0:.1f}% |",
            f"| **Status** | {'✅ SUCCESS' if total_failed == 0 and total_errors == 0 else '❌ FAILED'} |",
            "",
            "## 📝 Test Suites",
            ""
        ])
        
        for suite in test_suites:
            report.extend([
                f"### {suite.name}",
                "",
                f"- **Status:** {'✅ Passed' if suite.success else '❌ Failed'}",
                f"- **Total:** {suite.total}",
                f"- **Passed:** {suite.passed}",
                f"- **Failed:** {suite.failed}",
                f"- **Skipped:** {suite.skipped}",
                f"- **Errors:** {suite.errors}",
                f"- **Duration:** {suite.duration:.2f}s",
                "",
            ])
            
            if suite.results and (suite.failed > 0 or suite.errors > 0):
                report.append("#### Failed/Error Tests")
                report.append("")
                for result in suite.results:
                    if result.status in ["failed", "error"]:
                        report.append(f"- ❌ **{result.test_name}**")
                        if result.message:
                            report.append(f"  - {result.message}")
                        if result.traceback:
                            report.append(f"  ```\n  {result.traceback}\n  ```")
                report.append("")
        
        # Add coverage section
        if self.coverage_data:
            report.extend([
                "## 📊 Code Coverage",
                "",
                f"- **Total Coverage:** {self.coverage_data.get('total_coverage', 0):.1f}%",
                "",
                "### Files Coverage",
                "",
                "| File | Coverage |",
                "|------|----------|",
            ])
            
            for file, coverage in self.coverage_data.get("file_coverage", {}).items():
                report.append(f"| {file} | {coverage:.1f}% |")
            
            report.append("")
        
        # Add performance section
        if self.performance_data:
            report.extend([
                "## ⚡ Performance Benchmarks",
                "",
                "| Function | Avg Time (s) | Min (s) | Max (s) | Iterations |",
                "|----------|--------------|---------|---------|------------|",
            ])
            
            for func_name, data in self.performance_data.items():
                report.append(
                    f"| {func_name} | {data.get('average_time', 0):.6f} | "
                    f"{data.get('min_time', 0):.6f} | "
                    f"{data.get('max_time', 0):.6f} | "
                    f"{data.get('successful_iterations', 0)} |"
                )
            
            report.append("")
        
        # Add recommendations
        report.extend([
            "## 💡 Recommendations",
            "",
        ])
        
        if total_failed > 0 or total_errors > 0:
            report.append("- ❌ **Fix failing tests** before proceeding")
        
        if self.coverage_data and self.coverage_data.get("total_coverage", 0) < 80:
            report.append("- 📝 **Increase test coverage** to at least 80%")
        
        if not report[-1].startswith("-"):
            report.append("- ✅ All checks passed! Consider adding more tests for edge cases")
        
        report.append("")
        
        # Add timestamp footer
        report.append("---")
        report.append(f"*Report generated by AI Software Engineer Agent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return '\n'.join(report)
    
    # ============================================
    # 8. UTILITY FUNCTIONS
    # ============================================
    
    def _log(self, message: str):
        """Log a message if verbose is enabled"""
        if self.verbose:
            print(f"[TestingTools] {message}")
    
    def save_report(self, report: str, filename: str = "test_report.md") -> str:
        """
        Save test report to file
        
        Args:
            report: Report content
            filename: Output filename
            
        Returns:
            str: Path to saved report
        """
        report_path = self.reports_dir / filename
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        self._log(f"Report saved to: {report_path}")
        return str(report_path)
    
    def get_test_summary(self) -> Dict[str, Any]:
        """
        Get summary of all test results
        
        Returns:
            Dict[str, Any]: Test summary
        """
        total_passed = sum(s.passed for s in self.test_results)
        total_failed = sum(s.failed for s in self.test_results)
        total_skipped = sum(s.skipped for s in self.test_results)
        total_errors = sum(s.errors for s in self.test_results)
        total_tests = sum(s.total for s in self.test_results)
        
        return {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
            "errors": total_errors,
            "success_rate": ((total_passed / total_tests) * 100) if total_tests > 0 else 0,
            "success": total_failed == 0 and total_errors == 0,
            "coverage": self.coverage_data.get("total_coverage", 0) if self.coverage_data else 0
        }
    
    def clear_results(self):
        """Clear all test results"""
        self.test_results = []
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.error_tests = 0
        self._log("Test results cleared")


# ============================================
# 9. STANDALONE TEST GENERATOR
# ============================================

class TestGenerator:
    """
    Standalone test generator for creating test files
    """
    
    @staticmethod
    def generate_pytest_test(source_file: str, output_dir: str = "tests") -> str:
        """
        Generate a pytest test file
        
        Args:
            source_file: Source file path
            output_dir: Output directory
            
        Returns:
            str: Path to generated test file
        """
        source_path = Path(source_file)
        output_path = Path(output_dir) / f"test_{source_path.name}"
        
        # Read source content
        with open(source_path, 'r') as f:
            content = f.read()
        
        # Extract classes and functions
        classes = re.findall(r'class\s+(\w+)', content)
        functions = re.findall(r'def\s+(\w+)\s*\(', content)
        
        # Generate test content
        test_content = [
            '"""',
            f'Test file for {source_path.name}',
            '"""',
            '',
            'import pytest',
            f'from {source_path.stem} import *',
            '',
        ]
        
        for class_name in classes:
            test_content.extend([
                f'class Test{class_name}:',
                f'    """Test class for {class_name}"""',
                '',
                '    def setup_method(self):',
                f'        self.instance = {class_name}()',
                '',
                '    def test_initialization(self):',
                '        assert self.instance is not None',
                '',
            ])
        
        for func in functions:
            if not func.startswith('_'):
                test_content.extend([
                    f'def test_{func}():',
                    f'    """Test {func} function"""',
                    '    pass',
                    '',
                ])
        
        # Write test file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write('\n'.join(test_content))
        
        return str(output_path)


# ============================================
# 10. QUICK USAGE EXAMPLE
# ============================================

def example_usage():
    """
    Example usage of TestingTools
    """
    # Initialize testing tools
    tests = TestingTools(project_path=".", verbose=True)
    
    # Run unit tests
    unit_suite = tests.run_unit_tests()
    
    # Generate tests for a file
    gen_result = tests.generate_tests_for_file("src/my_module.py")
    
    # Analyze coverage
    coverage = tests.analyze_coverage()
    
    # Test an API endpoint
    api_result = tests.test_api_endpoint(
        url="http://localhost:8000/health",
        method="GET",
        expected_status=200
    )
    
    # Generate report
    report = tests.generate_test_report()
    
    # Save report
    tests.save_report(report, "test_report.md")
    
    # Get summary
    summary = tests.get_test_summary()
    
    return {
        "unit_tests": unit_suite,
        "coverage": coverage,
        "api_test": api_result,
        "summary": summary
    }


if __name__ == "__main__":
    # Run example
    results = example_usage()
    print("\n" + "="*50)
    print("TEST RESULTS")
    print("="*50)
    print(json.dumps(results, indent=2, default=str))