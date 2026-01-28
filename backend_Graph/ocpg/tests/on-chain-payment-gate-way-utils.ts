import { newMockEvent } from "matchstick-as"
import { ethereum, BigInt, Address } from "@graphprotocol/graph-ts"
import {
  IntentUpdated,
  MerchantRegistered,
  OwnershipTransferred,
  Paid,
  Paused,
  PaymentIntentCreated,
  TokenDisabled,
  TokenEnabled,
  Unpaused
} from "../generated/OnChainPaymentGateWay/OnChainPaymentGateWay"

export function createIntentUpdatedEvent(
  payId: BigInt,
  customer: Address,
  amount: BigInt,
  token: Address,
  updatedAt: BigInt
): IntentUpdated {
  let intentUpdatedEvent = changetype<IntentUpdated>(newMockEvent())

  intentUpdatedEvent.parameters = new Array()

  intentUpdatedEvent.parameters.push(
    new ethereum.EventParam("payId", ethereum.Value.fromUnsignedBigInt(payId))
  )
  intentUpdatedEvent.parameters.push(
    new ethereum.EventParam("customer", ethereum.Value.fromAddress(customer))
  )
  intentUpdatedEvent.parameters.push(
    new ethereum.EventParam("amount", ethereum.Value.fromUnsignedBigInt(amount))
  )
  intentUpdatedEvent.parameters.push(
    new ethereum.EventParam("token", ethereum.Value.fromAddress(token))
  )
  intentUpdatedEvent.parameters.push(
    new ethereum.EventParam(
      "updatedAt",
      ethereum.Value.fromUnsignedBigInt(updatedAt)
    )
  )

  return intentUpdatedEvent
}

export function createMerchantRegisteredEvent(
  merchant: Address,
  registeredAt: BigInt,
  businessName: string
): MerchantRegistered {
  let merchantRegisteredEvent = changetype<MerchantRegistered>(newMockEvent())

  merchantRegisteredEvent.parameters = new Array()

  merchantRegisteredEvent.parameters.push(
    new ethereum.EventParam("merchant", ethereum.Value.fromAddress(merchant))
  )
  merchantRegisteredEvent.parameters.push(
    new ethereum.EventParam(
      "registeredAt",
      ethereum.Value.fromUnsignedBigInt(registeredAt)
    )
  )
  merchantRegisteredEvent.parameters.push(
    new ethereum.EventParam(
      "businessName",
      ethereum.Value.fromString(businessName)
    )
  )

  return merchantRegisteredEvent
}

export function createOwnershipTransferredEvent(
  previousOwner: Address,
  newOwner: Address
): OwnershipTransferred {
  let ownershipTransferredEvent =
    changetype<OwnershipTransferred>(newMockEvent())

  ownershipTransferredEvent.parameters = new Array()

  ownershipTransferredEvent.parameters.push(
    new ethereum.EventParam(
      "previousOwner",
      ethereum.Value.fromAddress(previousOwner)
    )
  )
  ownershipTransferredEvent.parameters.push(
    new ethereum.EventParam("newOwner", ethereum.Value.fromAddress(newOwner))
  )

  return ownershipTransferredEvent
}

export function createPaidEvent(
  payId: BigInt,
  amount: BigInt,
  paidAt: BigInt
): Paid {
  let paidEvent = changetype<Paid>(newMockEvent())

  paidEvent.parameters = new Array()

  paidEvent.parameters.push(
    new ethereum.EventParam("payId", ethereum.Value.fromUnsignedBigInt(payId))
  )
  paidEvent.parameters.push(
    new ethereum.EventParam("amount", ethereum.Value.fromUnsignedBigInt(amount))
  )
  paidEvent.parameters.push(
    new ethereum.EventParam("paidAt", ethereum.Value.fromUnsignedBigInt(paidAt))
  )

  return paidEvent
}

export function createPausedEvent(account: Address): Paused {
  let pausedEvent = changetype<Paused>(newMockEvent())

  pausedEvent.parameters = new Array()

  pausedEvent.parameters.push(
    new ethereum.EventParam("account", ethereum.Value.fromAddress(account))
  )

  return pausedEvent
}

export function createPaymentIntentCreatedEvent(
  payId: BigInt,
  customer: Address,
  amount: BigInt,
  merchant: Address,
  createdAt: BigInt,
  expiryTime: BigInt
): PaymentIntentCreated {
  let paymentIntentCreatedEvent =
    changetype<PaymentIntentCreated>(newMockEvent())

  paymentIntentCreatedEvent.parameters = new Array()

  paymentIntentCreatedEvent.parameters.push(
    new ethereum.EventParam("payId", ethereum.Value.fromUnsignedBigInt(payId))
  )
  paymentIntentCreatedEvent.parameters.push(
    new ethereum.EventParam("customer", ethereum.Value.fromAddress(customer))
  )
  paymentIntentCreatedEvent.parameters.push(
    new ethereum.EventParam("amount", ethereum.Value.fromUnsignedBigInt(amount))
  )
  paymentIntentCreatedEvent.parameters.push(
    new ethereum.EventParam("merchant", ethereum.Value.fromAddress(merchant))
  )
  paymentIntentCreatedEvent.parameters.push(
    new ethereum.EventParam(
      "createdAt",
      ethereum.Value.fromUnsignedBigInt(createdAt)
    )
  )
  paymentIntentCreatedEvent.parameters.push(
    new ethereum.EventParam(
      "expiryTime",
      ethereum.Value.fromUnsignedBigInt(expiryTime)
    )
  )

  return paymentIntentCreatedEvent
}

export function createTokenDisabledEvent(_token: Address): TokenDisabled {
  let tokenDisabledEvent = changetype<TokenDisabled>(newMockEvent())

  tokenDisabledEvent.parameters = new Array()

  tokenDisabledEvent.parameters.push(
    new ethereum.EventParam("_token", ethereum.Value.fromAddress(_token))
  )

  return tokenDisabledEvent
}

export function createTokenEnabledEvent(_token: Address): TokenEnabled {
  let tokenEnabledEvent = changetype<TokenEnabled>(newMockEvent())

  tokenEnabledEvent.parameters = new Array()

  tokenEnabledEvent.parameters.push(
    new ethereum.EventParam("_token", ethereum.Value.fromAddress(_token))
  )

  return tokenEnabledEvent
}

export function createUnpausedEvent(account: Address): Unpaused {
  let unpausedEvent = changetype<Unpaused>(newMockEvent())

  unpausedEvent.parameters = new Array()

  unpausedEvent.parameters.push(
    new ethereum.EventParam("account", ethereum.Value.fromAddress(account))
  )

  return unpausedEvent
}
