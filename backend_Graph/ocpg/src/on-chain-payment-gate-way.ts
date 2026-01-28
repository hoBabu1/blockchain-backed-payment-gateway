import {
  IntentUpdated as IntentUpdatedEvent,
  MerchantRegistered as MerchantRegisteredEvent,
  OwnershipTransferred as OwnershipTransferredEvent,
  Paid as PaidEvent,
  Paused as PausedEvent,
  PaymentIntentCreated as PaymentIntentCreatedEvent,
  TokenDisabled as TokenDisabledEvent,
  TokenEnabled as TokenEnabledEvent,
  Unpaused as UnpausedEvent
} from "../generated/OnChainPaymentGateWay/OnChainPaymentGateWay"
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
} from "../generated/schema"

export function handleIntentUpdated(event: IntentUpdatedEvent): void {
  let entity = new IntentUpdated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.payId = event.params.payId
  entity.customer = event.params.customer
  entity.amount = event.params.amount
  entity.token = event.params.token
  entity.updatedAt = event.params.updatedAt

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleMerchantRegistered(event: MerchantRegisteredEvent): void {
  let entity = new MerchantRegistered(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.merchant = event.params.merchant
  entity.registeredAt = event.params.registeredAt
  entity.businessName = event.params.businessName

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleOwnershipTransferred(
  event: OwnershipTransferredEvent
): void {
  let entity = new OwnershipTransferred(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.previousOwner = event.params.previousOwner
  entity.newOwner = event.params.newOwner

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handlePaid(event: PaidEvent): void {
  let entity = new Paid(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.payId = event.params.payId
  entity.amount = event.params.amount
  entity.paidAt = event.params.paidAt

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handlePaused(event: PausedEvent): void {
  let entity = new Paused(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.account = event.params.account

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handlePaymentIntentCreated(
  event: PaymentIntentCreatedEvent
): void {
  let entity = new PaymentIntentCreated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.payId = event.params.payId
  entity.customer = event.params.customer
  entity.amount = event.params.amount
  entity.merchant = event.params.merchant
  entity.createdAt = event.params.createdAt
  entity.expiryTime = event.params.expiryTime

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleTokenDisabled(event: TokenDisabledEvent): void {
  let entity = new TokenDisabled(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity._token = event.params._token

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleTokenEnabled(event: TokenEnabledEvent): void {
  let entity = new TokenEnabled(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity._token = event.params._token

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleUnpaused(event: UnpausedEvent): void {
  let entity = new Unpaused(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.account = event.params.account

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}
