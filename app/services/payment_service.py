COMMISSION_RATE = 0.05  # 5% de commission

def calculate_commission(amount: float) -> float:
    return round(amount * COMMISSION_RATE, 2)

def get_payment_summary(amount: float, payment_method: str, rider_payment_phone: str) -> dict:
    commission = calculate_commission(amount)
    return {
        "amount": amount,
        "commission": commission,
        "rider_receives": round(amount - commission, 2),
        "payment_method": payment_method,
        "rider_payment_phone": rider_payment_phone,
        "instructions": f"Envoyez {amount} FCFA au {rider_payment_phone} via {payment_method.replace('_', ' ').title()}",
    }