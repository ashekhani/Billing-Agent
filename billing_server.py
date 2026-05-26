from mcp.server.fastmcp import FastMCP

mcp = FastMCP("billing-agent")

@mcp.tool()
def get_bill_summary(member_id: str) -> str:
    """Get the billing summary for a member.

    Args:
        member_id: The unique ID of the member (e.g. 12345)
    """
    mock_data = {
        "12345": {
            "name": "John Smith",
            "plan": "Gold PPO",
            "status": "Active",
            "claims": 3,
            "total_billed": "$4,200.00",
            "total_paid": "$3,800.00",
            "balance_due": "$400.00",
            "last_claim": "Claim #C-881 — Partial payment flag detected"
        },
        "67890": {
            "name": "Jane Doe",
            "plan": "Silver HMO",
            "status": "Active",
            "claims": 1,
            "total_billed": "$1,500.00",
            "total_paid": "$1,500.00",
            "balance_due": "$0.00",
            "last_claim": "Claim #C-774 — Fully paid"
        }
    }

    if member_id not in mock_data:
        return f"No billing records found for member ID {member_id}."

    d = mock_data[member_id]
    return f"""
Member: {d['name']}
Member ID: {member_id}
Plan: {d['plan']}
Status: {d['status']}
Total Claims: {d['claims']}
Total Billed: {d['total_billed']}
Total Paid: {d['total_paid']}
Balance Due: {d['balance_due']}
Last Claim: {d['last_claim']}
"""

if __name__ == "__main__":
    mcp.run(transport='stdio')
