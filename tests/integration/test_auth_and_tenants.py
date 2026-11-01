import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from services.api.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "enterprise-rag-api"

@pytest.mark.asyncio
async def test_auth_and_tenant_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"user_{uuid.uuid4().hex[:6]}@enterprise.com"
        password = "SecurePassword123!"

        # 1. Register User
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password
        })
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        token = reg_data["access_token"]
        user_id = reg_data["user_id"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 2. Login User
        login_res = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password
        })
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # 3. Invalid Login -> Check Standard Error Envelope
        bad_login = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "WrongPassword!"
        })
        assert bad_login.status_code == 401
        bad_json = bad_login.json()
        assert "error" in bad_json
        assert bad_json["error"]["code"] == "INVALID_CREDENTIALS"
        assert "request_id" in bad_json["error"]

        # 4. GET /me (Initially no tenants)
        me_res = await client.get("/api/v1/me", headers=auth_headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == email
        assert len(me_res.json()["tenants"]) == 0

        # 5. Create Tenant Workspace
        slug = f"workspace-{uuid.uuid4().hex[:8]}"
        tenant_res = await client.post("/api/v1/tenants", headers=auth_headers, json={
            "name": "Cloud Intelligence",
            "slug": slug
        })
        assert tenant_res.status_code == 201
        tenant_data = tenant_res.json()
        tenant_id = tenant_data["id"]
        assert tenant_data["role"] == "owner"
        assert tenant_data["slug"] == slug

        # 6. GET /me (Should now show the workspace)
        me_after = await client.get("/api/v1/me", headers=auth_headers)
        assert len(me_after.json()["tenants"]) == 1
        assert me_after.json()["tenants"][0]["id"] == tenant_id
        assert me_after.json()["tenants"][0]["role"] == "owner"

        # 7. Add Member to Workspace
        colleague_email = f"colleague_{uuid.uuid4().hex[:6]}@enterprise.com"
        add_res = await client.post(
            f"/api/v1/tenants/{tenant_id}/members",
            headers=auth_headers,
            json={"email": colleague_email, "role": "member"}
        )
        assert add_res.status_code == 201
        assert add_res.json()["email"] == colleague_email
        assert add_res.json()["role"] == "member"

        # 8. List Members
        members_res = await client.get(f"/api/v1/tenants/{tenant_id}/members", headers=auth_headers)
        assert members_res.status_code == 200
        members = members_res.json()
        assert len(members) == 2  # Owner + Colleague

        # 9. Tenant Isolation: Create User B and verify they CANNOT access User A's workspace
        user_b_email = f"user_b_{uuid.uuid4().hex[:6]}@other.com"
        b_reg = await client.post("/api/v1/auth/register", json={
            "email": user_b_email,
            "password": password
        })
        b_token = b_reg.json()["access_token"]
        b_headers = {"Authorization": f"Bearer {token_b}" if "token_b" in locals() else f"Bearer {b_token}"}

        # Attempt to access User A's workspace members -> Must return 404 (Contract anti-probing principle)
        b_access = await client.get(f"/api/v1/tenants/{tenant_id}/members", headers=b_headers)
        assert b_access.status_code == 404
        assert b_access.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
