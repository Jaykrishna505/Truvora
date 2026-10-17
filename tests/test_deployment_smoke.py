import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import main


class DeploymentSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_signup_login_and_dashboard_with_isolated_database(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            with patch.object(main, "DATA_DIR", data), patch.object(main, "DB_PATH", data / "app.db"):
                main.init_db()
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app), base_url="http://test"
                ) as client:
                    self.assertEqual((await client.get("/")).status_code, 200)
                    self.assertEqual((await client.get("/api/me")).status_code, 401)
                    registered = await client.post("/api/auth/register", json={
                        "businessName": "Deployment Test",
                        "businessType": "restaurant",
                        "email": "deploy@example.test",
                        "password": "deployment-test-password",
                    })
                    self.assertEqual(registered.status_code, 200, registered.text)
                    self.assertEqual((await client.get("/app")).status_code, 200)
                    me = await client.get("/api/me")
                    self.assertEqual(me.status_code, 200)
                    self.assertEqual(me.json()["business"]["businessType"], "restaurant")
                    client.cookies.clear()
                    denied = await client.post("/api/auth/login", json={
                        "email": "deploy@example.test", "password": "wrong-password"
                    })
                    self.assertEqual(denied.status_code, 401)
                    login = await client.post("/api/auth/login", json={
                        "email": "deploy@example.test", "password": "deployment-test-password"
                    })
                    self.assertEqual(login.status_code, 200)


if __name__ == "__main__":
    unittest.main()
