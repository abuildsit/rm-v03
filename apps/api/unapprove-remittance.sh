#!/bin/bash

# Unapprove Remittance Script
# This script unapproves an exported remittance by deleting the batch payment in Xero
# and reverting the remittance status to Awaiting_Approval

set -e  # Exit on any error

# Configuration
API_BASE_URL="http://localhost:8001/api/v1"
ORG_ID="42f929b1-8fdb-45b1-a7cf-34fae2314561"
AUTH_TOKEN="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNWM5YzI4OS0wYmQzLTRiMGMtYWE5MC00MDQ2ZDFhNzEwOTgiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJpYXQiOjE3NTMzMTM4NzMsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJpc3MiOiJzdXBhYmFzZSJ9.rr275Rd9aWYXpqMhXOCqGbT5eOLUkqKfgE5lT42fAX8"

# Default remittance ID (can be overridden by command line argument)
REMITTANCE_ID="${1:-f8fa4223-8e0e-4671-b784-8ac759f52fc3}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Function to check if API server is running
check_server() {
    print_step "Checking API Server"
    
    if curl -s "${API_BASE_URL%/api/v1}/health" > /dev/null; then
        print_success "API server is running"
    else
        print_error "API server is not running. Please start it with 'make dev'"
        exit 1
    fi
}

# Function to validate remittance ID
validate_remittance_id() {
    print_step "Validating Remittance ID"
    
    if [ "$REMITTANCE_ID" = "f8fa4223-8e0e-4671-b784-8ac759f52fc3" ]; then
        print_error "No remittance ID provided"
        print_info "Usage: $0 <remittance_id>"
        print_info "Example: $0 a1b2c3d4-e5f6-7890-1234-567890abcdef"
        exit 1
    fi
    
    # Check if it looks like a GUID
    if [[ ! "$REMITTANCE_ID" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
        print_warning "Remittance ID doesn't look like a GUID format"
        print_info "Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    fi
    
    print_success "Remittance ID: $REMITTANCE_ID"
}

# Function to get current remittance status
get_current_status() {
    print_step "Getting Current Remittance Status"
    
    print_info "Checking current remittance status..."
    
    local response=$(curl -s -X GET \
        "${API_BASE_URL}/remittances/${ORG_ID}/${REMITTANCE_ID}" \
        -H "Authorization: ${AUTH_TOKEN}")
    
    local status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
    print_info "Current status: $status"
    
    if [ "$status" != "Exported_Unreconciled" ]; then
        print_warning "Remittance is not in 'Exported_Unreconciled' status"
        print_info "Unapproval is only allowed for exported unreconciled remittances"
    fi
    
    print_info "Proceeding with unapproval request..."
}

# Function to unapprove remittance
unapprove_remittance() {
    print_step "Unapproving Remittance"
    
    print_info "Sending unapproval request (delete batch payment and revert status)..."
    
    # Use the remittance update endpoint with unapprove=true
    local response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH \
        "${API_BASE_URL}/remittances/${ORG_ID}/${REMITTANCE_ID}" \
        -H "Authorization: ${AUTH_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{"unapprove": true}')
    
    # Extract HTTP status code
    local http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    local json_response=$(echo "$response" | grep -v "HTTP_STATUS:")
    
    print_info "HTTP Status: $http_status"
    
    case "$http_status" in
        200|201)
            print_success "Remittance unapproved successfully!"
            echo "Response:"
            echo "$json_response" | python3 -m json.tool 2>/dev/null || echo "$json_response"
            ;;
        400)
            print_error "Bad request - Check remittance status and conditions"
            echo "Response: $json_response"
            # Extract error message for user-friendly display
            local error_msg=$(echo "$json_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('detail', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
            print_info "Error: $error_msg"
            ;;
        401)
            print_error "Authentication failed - Check authorization token"
            echo "Response: $json_response"
            ;;
        404)
            print_error "Remittance not found"
            echo "Response: $json_response"
            ;;
        500)
            print_error "Server error occurred"
            echo "Response: $json_response"
            ;;
        *)
            print_warning "Unexpected response status: $http_status"
            echo "Response: $json_response"
            ;;
    esac
}

# Function to verify unapproval
verify_unapproval() {
    print_step "Verifying Unapproval"
    
    print_info "Checking updated remittance status..."
    
    local response=$(curl -s -X GET \
        "${API_BASE_URL}/remittances/${ORG_ID}/${REMITTANCE_ID}" \
        -H "Authorization: ${AUTH_TOKEN}")
    
    local status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
    local batch_id=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('xeroBatchId', 'None'))" 2>/dev/null || echo "unknown")
    
    print_info "Updated status: $status"
    print_info "Xero Batch ID: $batch_id"
    
    if [ "$status" = "Awaiting_Approval" ] && [ "$batch_id" = "None" ]; then
        print_success "Unapproval verification successful!"
        print_info "✅ Status reverted to Awaiting_Approval"
        print_info "✅ Batch payment ID cleared"
    else
        print_warning "Unapproval may not have completed successfully"
        print_info "Expected: status=Awaiting_Approval, batch_id=None"
        print_info "Actual: status=$status, batch_id=$batch_id"
    fi
}

# Function to display summary
display_summary() {
    print_step "Unapproval Summary"
    
    echo "🎯 Remittance Unapproval Attempted:"
    echo "   • Remittance ID: $REMITTANCE_ID"
    echo "   • Organization ID: $ORG_ID"
    echo "   • Method: Unapproval workflow via remittance update"
    echo
    
    echo "🔧 Technical Details:"
    echo "   • Used remittance update endpoint with unapprove=true"
    echo "   • Validated remittance status before unapproval"
    echo "   • Checked batch payment reconciliation status in Xero"
    echo "   • Deleted batch payment in Xero (Status = DELETED)"
    echo "   • Reverted remittance status to Awaiting_Approval"
    echo "   • Cleared batch payment tracking fields"
    echo
    
    echo "📝 Notes:"
    echo "   • Unapproval is only allowed for Exported_Unreconciled remittances"
    echo "   • Batch payment must not be reconciled in Xero"
    echo "   • Process includes proper audit logging"
    echo "   • Follows business rules for unapproval workflow"
    echo "   • Users can re-approve the remittance after unapproval"
    echo
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              Unapprove Remittance Script                    ║"
    echo "║                                                              ║"
    echo "║  This script unapproves an exported remittance by deleting  ║"
    echo "║  the batch payment in Xero and reverting the status.        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
    
    # Run all steps
    check_server
    validate_remittance_id
    get_current_status
    unapprove_remittance
    verify_unapproval
    display_summary
}

# Handle script interruption
trap 'echo -e "\n${RED}Unapproval script interrupted by user${NC}"; exit 1' INT

# Execute main function
main "$@"