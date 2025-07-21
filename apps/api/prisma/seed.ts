import { PrismaClient } from '../generated/prisma'

const prisma = new PrismaClient()

async function main() {
  console.log('🌱 Starting database seed...')

  // Seed invoice data
  const invoices = [
    {
      id: 'ac453251-76ff-4cde-8ed1-486e7c7b8605',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '0a874603-e713-4bfe-8a23-e22ca3ab611c',
      invoice_number: 'PMI-SPI-426425',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 542.73,
      currency_code: 'AUD',
      reference: 'KING Sean - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: 'c60437d7-cafd-49ee-a949-a1389ade1ea7',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: 'b3b5a280-6818-4f41-9ba0-0d0e3fdbf11e',
      invoice_number: 'PMI-IOT46266',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 86.80,
      currency_code: 'AUD',
      reference: 'KING Sean - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: '1b0e86ed-8335-40ac-9c25-9af7c061b11d',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '56a8158f-658e-4425-88b1-7fa7b3fc6d33',
      invoice_number: 'PMI-INV-62775',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 587.43,
      currency_code: 'AUD',
      reference: 'CHANNON Rachel - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: '84fed409-19b5-4f7d-bfaf-2d7d8ca3860b',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '2f27fc5b-ede3-43fa-9187-9280a407452b',
      invoice_number: 'PMI-INV-62228',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 734.03,
      currency_code: 'AUD',
      reference: 'CHANNON Rachel - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: '034b66e0-9e29-43a1-b3b9-51cd7ded53a1',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: 'aa66d061-080a-40d9-a2e4-598bf5c23035',
      invoice_number: 'PMI-AAA777953',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 545.12,
      currency_code: 'AUD',
      reference: 'CHANNON Rachel - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: '14708462-7968-4fcf-8e09-e3c9c84f34e8',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '1c7a6a6e-4bb3-4954-98c1-ee4edfd4987a',
      invoice_number: 'PMI-48149',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 119.45,
      currency_code: 'AUD',
      reference: 'CHANNON Rachel - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: 'b5018d37-b561-4f33-b97c-9900764dc887',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '4a07830c-8591-454e-af04-bfa9504283a3',
      invoice_number: 'PMI-42708',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 283.58,
      currency_code: 'AUD',
      reference: 'PARRISH Samuel - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: '6e9b61be-5005-4391-8694-2a97f305d8be',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: 'b2689daa-04a2-4f3d-807b-2969ca01f076',
      invoice_number: 'PMI-34427',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 509.08,
      currency_code: 'AUD',
      reference: 'KING Sean - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: 'd38e5288-a5cf-4bb9-a531-7dd8c33f05b5',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '32ae7f27-ace0-492d-91a5-1407870168f5',
      invoice_number: 'PMI-34289',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 2474.33,
      currency_code: 'AUD',
      reference: 'KING Sean - Plan Managed',
      is_discounted: false,
      has_errors: false
    },
    {
      id: '744d163e-a971-4cb6-b776-865c13ad690e',
      organization_id: '42f929b1-8fdb-45b1-a7cf-34fae2314561',
      invoice_id: '0aa277f9-7ba4-45d3-a781-4ba9982b92cb',
      invoice_number: 'PMI-337',
      contact_name: 'PRODA',
      contact_id: 'a74e319d-db70-4874-8fda-411771f82df0',
      invoice_date: new Date('2024-05-16'),
      due_date: new Date('2024-05-17'),
      status: 'DELETED' as const,
      amount_due: 0.00,
      amount_paid: 0.00,
      total: 140.00,
      currency_code: 'AUD',
      reference: 'CHANNON Rachel - Plan Managed',
      is_discounted: false,
      has_errors: false
    }
  ]

  // Create invoices using createMany for efficiency
  const result = await prisma.invoices.createMany({
    data: invoices,
    skipDuplicates: true
  })

  console.log(`✅ Created ${result.count} invoices`)
  console.log('🌱 Seed completed successfully!')
}

main()
  .catch((e) => {
    console.error('❌ Seed failed:', e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })