"""
Playwright automated tests for News Agent application.
Tests for bugs, errors, and functional issues.
"""
import pytest
from playwright.sync_api import Page, expect, Error
import json
import time


class TestNewsAgentBugs:
    """Test suite to detect bugs in News Agent application."""

    BASE_URL = "http://localhost:5000"

    def test_homepage_loads_without_errors(self, page: Page):
        """Test that homepage loads and has no console errors."""
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # Navigate to homepage
        try:
            response = page.goto(self.BASE_URL, wait_until="networkidle", timeout=10000)
            assert response.ok, f"Homepage returned status {response.status}"
        except Error as e:
            pytest.fail(f"Failed to load homepage: {str(e)}")

        # Check for console errors
        page.wait_for_timeout(2000)  # Wait for any async errors

        if console_errors:
            print(f"\n🐛 BUG FOUND: Console errors on homepage:")
            for error in console_errors:
                print(f"  - {error}")
            pytest.fail(f"Found {len(console_errors)} console errors")

    def test_api_health_endpoint(self, page: Page):
        """Test /api/health endpoint."""
        try:
            response = page.request.get(f"{self.BASE_URL}/api/health")
            assert response.ok, f"Health endpoint returned {response.status}"

            data = response.json()
            assert "status" in data, "Health response missing 'status' field"
            assert data["status"] == "healthy", f"Unhealthy status: {data.get('status')}"

        except Exception as e:
            print(f"\n🐛 BUG FOUND: Health endpoint failed: {str(e)}")
            pytest.fail(str(e))

    def test_api_articles_endpoint(self, page: Page):
        """Test /api/news/articles endpoint."""
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            response = page.request.get(f"{self.BASE_URL}/api/news/articles?limit=10")
            assert response.ok, f"Articles endpoint returned {response.status}"

            data = response.json()
            assert "success" in data, "Response missing 'success' field"

            if not data.get("success"):
                error = data.get("error", "Unknown error")
                print(f"\n🐛 BUG FOUND: Articles API returned error: {error}")
                pytest.fail(f"API error: {error}")

        except Exception as e:
            print(f"\n🐛 BUG FOUND: Articles endpoint failed: {str(e)}")
            pytest.fail(str(e))

    def test_api_sources_endpoint(self, page: Page):
        """Test /api/sources endpoint."""
        try:
            response = page.request.get(f"{self.BASE_URL}/api/sources")
            assert response.ok, f"Sources endpoint returned {response.status}"

            data = response.json()
            assert "success" in data, "Response missing 'success' field"
            assert data.get("success"), f"API error: {data.get('error')}"

        except Exception as e:
            print(f"\n🐛 BUG FOUND: Sources endpoint failed: {str(e)}")
            pytest.fail(str(e))

    def test_api_stats_endpoint(self, page: Page):
        """Test /api/stats endpoint."""
        try:
            response = page.request.get(f"{self.BASE_URL}/api/stats")
            assert response.ok, f"Stats endpoint returned {response.status}"

            data = response.json()
            assert "success" in data, "Response missing 'success' field"

        except Exception as e:
            print(f"\n🐛 BUG FOUND: Stats endpoint failed: {str(e)}")
            pytest.fail(str(e))

    def test_articles_page_navigation(self, page: Page):
        """Test navigation to articles page."""
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            page.goto(f"{self.BASE_URL}/articles", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(2000)

            if console_errors:
                print(f"\n🐛 BUG FOUND: Console errors on articles page:")
                for error in console_errors:
                    print(f"  - {error}")

        except Error as e:
            print(f"\n🐛 BUG FOUND: Failed to load articles page: {str(e)}")
            pytest.fail(str(e))

    def test_sources_page_navigation(self, page: Page):
        """Test navigation to sources page."""
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            page.goto(f"{self.BASE_URL}/sources", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(2000)

            if console_errors:
                print(f"\n🐛 BUG FOUND: Console errors on sources page:")
                for error in console_errors:
                    print(f"  - {error}")

        except Error as e:
            print(f"\n🐛 BUG FOUND: Failed to load sources page: {str(e)}")
            pytest.fail(str(e))

    def test_mobile_responsive(self, page: Page):
        """Test mobile responsiveness."""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})

        try:
            page.goto(self.BASE_URL, wait_until="networkidle")
            page.wait_for_timeout(1000)

            # Check for horizontal scroll
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")

            if scroll_width > client_width:
                print(f"\n🐛 BUG FOUND: Horizontal scroll on mobile (width: {scroll_width} > {client_width})")
                pytest.fail("Mobile horizontal scroll detected")

        except Error as e:
            print(f"\n🐛 BUG FOUND: Mobile responsive test failed: {str(e)}")
            pytest.fail(str(e))

    def test_javascript_errors_dashboard(self, page: Page):
        """Test for JavaScript errors on dashboard."""
        js_errors = []
        page.on("pageerror", lambda exc: js_errors.append(str(exc)))

        try:
            page.goto(self.BASE_URL, wait_until="networkidle")
            page.wait_for_timeout(3000)

            if js_errors:
                print(f"\n🐛 BUG FOUND: JavaScript errors detected:")
                for error in js_errors:
                    print(f"  - {error}")
                pytest.fail(f"Found {len(js_errors)} JavaScript errors")

        except Error as e:
            print(f"\n🐛 BUG FOUND: Dashboard test failed: {str(e)}")
            pytest.fail(str(e))

    def test_api_response_times(self, page: Page):
        """Test API response times."""
        slow_endpoints = []

        endpoints = [
            "/api/health",
            "/api/news/articles",
            "/api/sources",
            "/api/stats"
        ]

        for endpoint in endpoints:
            start_time = time.time()
            try:
                response = page.request.get(f"{self.BASE_URL}{endpoint}")
                elapsed = time.time() - start_time

                if elapsed > 5.0:  # 5 second threshold
                    slow_endpoints.append((endpoint, elapsed))
                    print(f"\n⚠️  PERFORMANCE: {endpoint} took {elapsed:.2f}s")

            except Exception as e:
                print(f"\n🐛 BUG FOUND: {endpoint} failed: {str(e)}")

        if slow_endpoints:
            print(f"\n⚠️  Found {len(slow_endpoints)} slow endpoints")

    def test_missing_templates(self, page: Page):
        """Test for missing template errors."""
        pages_to_test = [
            "/",
            "/home",
            "/articles",
            "/sources"
        ]

        for path in pages_to_test:
            try:
                response = page.goto(f"{self.BASE_URL}{path}", wait_until="domcontentloaded", timeout=10000)

                if response.status == 404:
                    print(f"\n🐛 BUG FOUND: 404 Not Found for {path}")
                elif response.status == 500:
                    print(f"\n🐛 BUG FOUND: 500 Internal Server Error for {path}")

            except Error as e:
                print(f"\n🐛 BUG FOUND: Failed to load {path}: {str(e)}")

    def test_api_error_handling(self, page: Page):
        """Test API error handling with invalid inputs."""
        test_cases = [
            ("/api/news/articles?limit=999999", "Large limit"),
            ("/api/news/articles?limit=-1", "Negative limit"),
            ("/api/news/articles?limit=abc", "Invalid limit type"),
            ("/api/sources/invalid_id", "Invalid source ID"),
        ]

        for endpoint, description in test_cases:
            try:
                response = page.request.get(f"{self.BASE_URL}{endpoint}")

                # Should handle gracefully, not crash
                if response.status == 500:
                    print(f"\n🐛 BUG FOUND: {description} caused 500 error at {endpoint}")

            except Exception as e:
                print(f"\n🐛 BUG FOUND: {description} caused exception: {str(e)}")


class TestUIBugs:
    """Test suite for UI-specific bugs."""

    BASE_URL = "http://localhost:5000"

    def test_page_title_exists(self, page: Page):
        """Test that pages have proper titles."""
        page.goto(self.BASE_URL)
        title = page.title()

        if not title or title == "":
            print("\n🐛 BUG FOUND: Homepage has no title")
            pytest.fail("Missing page title")

    def test_navigation_links(self, page: Page):
        """Test that navigation links work."""
        page.goto(self.BASE_URL)

        # Look for broken links
        links = page.locator("a[href]").all()
        broken_links = []

        for link in links[:10]:  # Test first 10 links only
            href = link.get_attribute("href")
            if href and href.startswith("/"):
                try:
                    response = page.request.get(f"{self.BASE_URL}{href}")
                    if response.status >= 400:
                        broken_links.append((href, response.status))
                except Exception as e:
                    broken_links.append((href, str(e)))

        if broken_links:
            print(f"\n🐛 BUG FOUND: Broken links detected:")
            for link, status in broken_links:
                print(f"  - {link}: {status}")
