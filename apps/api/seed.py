#!/usr/bin/env python3
import asyncio
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import jwt
from prisma.enums import InvoiceStatus, MemberStatus, OrganizationRole
from supabase import Client, create_client

from prisma import Prisma
from src.core.settings import settings

# Add the project root to Python path so we can import from src
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


async def setup_storage_bucket(supabase: Client):
    """Create and configure the remittance-files storage bucket"""
    print("🗂️ Setting up storage bucket...")

    try:
        # Check if bucket exists
        buckets = supabase.storage.list_buckets()
        bucket_exists = any(bucket.name == "remittance-files" for bucket in buckets)

        if not bucket_exists:
            # Create the bucket
            supabase.storage.create_bucket(
                "remittance-files",
                options={
                    "public": False,
                    "file_size_limit": 52428800,  # 50MB
                    "allowed_mime_types": ["application/pdf"],
                },
            )
            print("✅ Created storage bucket: remittance-files")
        else:
            print("ℹ️ Storage bucket already exists: remittance-files")

    except Exception as e:
        print(f"❌ Storage bucket setup failed: {e}")
        # Don't fail the entire seed if storage setup fails
        pass


async def main():
    print("🌱 Starting database seed...")

    prisma = Prisma()
    await prisma.connect()

    # Initialize Supabase client
    supabase: Client | None = (
        create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        if settings.SUPABASE_URL and settings.SUPABASE_KEY
        else None
    )

    try:
        # First create the organization that will own the invoices
        org_id = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
        second_org_id = "d85c4b2a-9f1e-4c7d-b8a9-f3e7d6c5b4a3"

        # Check if first organization exists, create if not
        existing_org = await prisma.organization.find_unique(where={"id": org_id})
        if not existing_org:
            await prisma.organization.create(
                data={
                    "id": org_id,
                    "name": "Test Organization",
                    "subscriptionTier": "basic",
                }
            )
            print(f"✅ Created organization: {org_id}")
        else:
            print(f"ℹ️ Organization already exists: {org_id}")

        # Check if second organization exists, create if not
        existing_second_org = await prisma.organization.find_unique(
            where={"id": second_org_id}
        )
        if not existing_second_org:
            await prisma.organization.create(
                data={
                    "id": second_org_id,
                    "name": "Second Test Organization",
                    "subscriptionTier": "premium",
                }
            )
            print(f"✅ Created second organization: {second_org_id}")
        else:
            print(f"ℹ️ Second organization already exists: {second_org_id}")

        # Create fake user data
        user_id = str(uuid.uuid4())
        profile_id = str(uuid.uuid4())
        auth_link_id = str(uuid.uuid4())
        fake_email = "test@example.com"

        # Check if profile exists, create if not
        existing_profile = await prisma.profile.find_unique(where={"email": fake_email})
        if not existing_profile:
            # Create profile
            profile = await prisma.profile.create(
                data={
                    "id": profile_id,
                    "email": fake_email,
                    "displayName": "Test User",
                    "lastAccessedOrgId": org_id,
                }
            )
            print(f"✅ Created profile: {profile.email}")

            # Create auth link
            auth_link = await prisma.authlink.create(
                data={
                    "id": auth_link_id,
                    "authId": user_id,
                    "profileId": profile_id,
                    "provider": "supabase",
                    "providerUserId": user_id,
                }
            )
            print(f"✅ Created auth link for user: {user_id}")

            # Create organization membership for first org
            membership = await prisma.organizationmember.create(
                data={
                    "profileId": profile_id,
                    "organizationId": org_id,
                    "role": OrganizationRole.admin,
                    "status": MemberStatus.active,
                }
            )
            print(f"✅ Created organization membership with role: {membership.role}")

            # Create organization membership for second org
            second_membership = await prisma.organizationmember.create(
                data={
                    "profileId": profile_id,
                    "organizationId": second_org_id,
                    "role": OrganizationRole.user,
                    "status": MemberStatus.active,
                }
            )
            print(
                f"✅ Created second organization membership with role: "
                f"{second_membership.role}"
            )

        else:
            print(f"ℹ️ Profile already exists: {fake_email}")
            profile = existing_profile
            # Get the auth link to extract user_id
            auth_link = await prisma.authlink.find_first(
                where={"profileId": existing_profile.id}
            )
            if auth_link:
                user_id = auth_link.authId or user_id

            # Check if user is already a member of the second organization
            existing_second_membership = await prisma.organizationmember.find_unique(
                where={
                    "profileId_organizationId": {
                        "profileId": existing_profile.id,
                        "organizationId": second_org_id,
                    }
                }
            )

            if not existing_second_membership:
                # Create organization membership for second org
                second_membership = await prisma.organizationmember.create(
                    data={
                        "profileId": existing_profile.id,
                        "organizationId": second_org_id,
                        "role": OrganizationRole.user,
                        "status": MemberStatus.active,
                    }
                )
                print(
                    f"✅ Added existing user to second organization with role: "
                    f"{second_membership.role}"
                )
            else:
                print("ℹ️ User already belongs to second organization")

        # Generate fake JWT token for testing
        # Use the same secret that's in the .env file
        jwt_secret = "super-secret-jwt-token-with-at-least-32-characters-long"
        jwt_payload = {
            "sub": user_id,  # subject (user ID)
            "email": fake_email,
            "iat": datetime.utcnow(),
            # Remove exp claim to make token valid forever (for testing only)
            "aud": "authenticated",
            "iss": "supabase",
        }

        fake_jwt = jwt.encode(jwt_payload, jwt_secret, algorithm="HS256")
        print(f"✅ Generated fake JWT token: {fake_jwt}")
        print("📋 Test user details:")
        print(f"   Email: {fake_email}")
        print(f"   Auth ID: {user_id}")
        print(f"   Profile ID: {profile_id}")
        print(f"   Organization ID: {org_id}")
        print(f"   Authorization Header: Bearer {fake_jwt}")

        # Seed invoice data
        invoices = [
            {
                "id": "ac453251-76ff-4cde-8ed1-486e7c7b8605",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "0a874603-e713-4bfe-8a23-e22ca3ab611c",
                "invoiceNumber": "PMI-SPI-426425",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("542.73"),
                "currencyCode": "AUD",
                "reference": "KING Sean - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "c60437d7-cafd-49ee-a949-a1389ade1ea7",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "b3b5a280-6818-4f41-9ba0-0d0e3fdbf11e",
                "invoiceNumber": "PMI-IOT46266",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("86.80"),
                "currencyCode": "AUD",
                "reference": "KING Sean - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "1b0e86ed-8335-40ac-9c25-9af7c061b11d",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "56a8158f-658e-4425-88b1-7fa7b3fc6d33",
                "invoiceNumber": "PMI-INV-62775",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("587.43"),
                "currencyCode": "AUD",
                "reference": "CHANNON Rachel - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "84fed409-19b5-4f7d-bfaf-2d7d8ca3860b",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "2f27fc5b-ede3-43fa-9187-9280a407452b",
                "invoiceNumber": "PMI-INV-62228",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("734.03"),
                "currencyCode": "AUD",
                "reference": "CHANNON Rachel - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "034b66e0-9e29-43a1-b3b9-51cd7ded53a1",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "aa66d061-080a-40d9-a2e4-598bf5c23035",
                "invoiceNumber": "PMI-AAA777953",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("545.12"),
                "currencyCode": "AUD",
                "reference": "CHANNON Rachel - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "14708462-7968-4fcf-8e09-e3c9c84f34e8",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "1c7a6a6e-4bb3-4954-98c1-ee4edfd4987a",
                "invoiceNumber": "PMI-48149",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("119.45"),
                "currencyCode": "AUD",
                "reference": "CHANNON Rachel - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "b5018d37-b561-4f33-b97c-9900764dc887",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "4a07830c-8591-454e-af04-bfa9504283a3",
                "invoiceNumber": "PMI-42708",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("283.58"),
                "currencyCode": "AUD",
                "reference": "PARRISH Samuel - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "6e9b61be-5005-4391-8694-2a97f305d8be",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "b2689daa-04a2-4f3d-807b-2969ca01f076",
                "invoiceNumber": "PMI-34427",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("509.08"),
                "currencyCode": "AUD",
                "reference": "KING Sean - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "d38e5288-a5cf-4bb9-a531-7dd8c33f05b5",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "32ae7f27-ace0-492d-91a5-1407870168f5",
                "invoiceNumber": "PMI-34289",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("2474.33"),
                "currencyCode": "AUD",
                "reference": "KING Sean - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
            {
                "id": "744d163e-a971-4cb6-b776-865c13ad690e",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "invoiceId": "0aa277f9-7ba4-45d3-a781-4ba9982b92cb",
                "invoiceNumber": "PMI-337",
                "contactName": "PRODA",
                "contactId": "a74e319d-db70-4874-8fda-411771f82df0",
                "invoiceDate": datetime(2024, 5, 16),
                "dueDate": datetime(2024, 5, 17),
                "status": InvoiceStatus.DELETED,
                "amountDue": Decimal("0.00"),
                "amountPaid": Decimal("0.00"),
                "total": Decimal("140.00"),
                "currencyCode": "AUD",
                "reference": "CHANNON Rachel - Plan Managed",
                "isDiscounted": False,
                "hasErrors": False,
            },
        ]

        # Create invoices using create_many for efficiency
        result = await prisma.invoice.create_many(data=invoices, skip_duplicates=True)

        print(f"✅ Created {result} invoices")

        # Seed bank account data
        bank_accounts = [
            {
                "id": "ba1e4a2c-9f3d-4b8e-a7c6-5d9e8f1a2b3c",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "xeroAccountId": "12345678-1234-1234-1234-123456789012",
                "xeroName": "Business Transaction Account",
                "xeroCode": "090",
                "type": "BANK",
                "status": "ACTIVE",
                "isDefault": True,
                "currencyCode": "AUD",
                "enablePaymentsToAccount": True,
                "bankAccountNumber": "062-001-12345678",
            },
            {
                "id": "ba2f5b3d-8e4c-4a7f-b6d5-4c8a7b2e3f1d",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "xeroAccountId": "87654321-4321-4321-4321-210987654321",
                "xeroName": "Business Savings Account",
                "xeroCode": "091",
                "type": "BANK",
                "status": "ACTIVE",
                "isDefault": False,
                "currencyCode": "AUD",
                "enablePaymentsToAccount": True,
                "bankAccountNumber": "062-001-87654321",
            },
            {
                "id": "ba3a6c4e-9d5b-4f8a-c7e6-3d9f8a1c4e2f",
                "organizationId": "42f929b1-8fdb-45b1-a7cf-34fae2314561",
                "xeroAccountId": "11111111-1111-1111-1111-111111111111",
                "xeroName": "Credit Card Account",
                "xeroCode": "092",
                "type": "CREDITCARD",
                "status": "ACTIVE",
                "isDefault": False,
                "currencyCode": "AUD",
                "enablePaymentsToAccount": False,
                "bankAccountNumber": "4111-1111-1111-1111",
            },
            {
                "id": "ba4a7d5f-8c6a-4e9b-d8f7-2c8e9b1d5f3a",
                "organizationId": "d85c4b2a-9f1e-4c7d-b8a9-f3e7d6c5b4a3",  # Second org
                "xeroAccountId": "22222222-2222-2222-2222-222222222222",
                "xeroName": "Second Org Main Account",
                "xeroCode": "093",
                "type": "BANK",
                "status": "ACTIVE",
                "isDefault": True,
                "currencyCode": "AUD",
                "enablePaymentsToAccount": True,
                "bankAccountNumber": "062-002-22222222",
            },
        ]

        # Create bank accounts using create_many for efficiency
        bank_result = await prisma.bankaccount.create_many(
            data=bank_accounts, skip_duplicates=True
        )

        print(f"✅ Created {bank_result} bank accounts")

        # Set up storage bucket if Supabase is configured
        if supabase:
            await setup_storage_bucket(supabase)
        else:
            print("ℹ️ Skipping storage bucket setup - Supabase not configured")

        print("🌱 Seed completed successfully!")

    except Exception as e:
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
