from .config import settings
from .models import Charge, Subscription
from .schemas import ChargeOut, PaymentOut, SubscriptionOut


def charge_to_out(charge: Charge) -> ChargeOut:
    return ChargeOut(
        id=charge.id,
        amount=float(charge.amount),
        currency=charge.currency,
        status=charge.status,
        description=charge.description,
        reference=charge.reference,
        metadata=charge.extra or {},
        checkout_url=f"{settings.checkout_base_url}/pay/{charge.id}",
        expires_at=charge.expires_at,
        paid_at=charge.paid_at,
        canceled_at=charge.canceled_at,
        refunded_at=charge.refunded_at,
        refund_reason=charge.refund_reason,
        created_at=charge.created_at,
        payment=PaymentOut.model_validate(charge.payment) if charge.payment else None,
    )


def subscription_to_out(sub: Subscription) -> SubscriptionOut:
    return SubscriptionOut(
        id=sub.id,
        plan_id=sub.plan_id,
        plan_name=sub.plan.name if sub.plan else None,
        customer_name=sub.customer_name,
        customer_email=sub.customer_email,
        customer_phone=sub.customer_phone,
        customer_line_id=sub.customer_line_id,
        customer_ref=sub.customer_ref,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        canceled_at=sub.canceled_at,
        ended_at=sub.ended_at,
        portal_url=f"{settings.checkout_base_url}/m/{sub.portal_token}" if sub.portal_token else None,
        created_at=sub.created_at,
    )
