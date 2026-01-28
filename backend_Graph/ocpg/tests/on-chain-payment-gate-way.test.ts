import {
  assert,
  describe,
  test,
  clearStore,
  beforeAll,
  afterAll
} from "matchstick-as/assembly/index"
import { BigInt, Address } from "@graphprotocol/graph-ts"
import { IntentUpdated } from "../generated/schema"
import { IntentUpdated as IntentUpdatedEvent } from "../generated/OnChainPaymentGateWay/OnChainPaymentGateWay"
import { handleIntentUpdated } from "../src/on-chain-payment-gate-way"
import { createIntentUpdatedEvent } from "./on-chain-payment-gate-way-utils"

// Tests structure (matchstick-as >=0.5.0)
// https://thegraph.com/docs/en/subgraphs/developing/creating/unit-testing-framework/#tests-structure

describe("Describe entity assertions", () => {
  beforeAll(() => {
    let payId = BigInt.fromI32(234)
    let customer = Address.fromString(
      "0x0000000000000000000000000000000000000001"
    )
    let amount = BigInt.fromI32(234)
    let token = Address.fromString("0x0000000000000000000000000000000000000001")
    let updatedAt = BigInt.fromI32(234)
    let newIntentUpdatedEvent = createIntentUpdatedEvent(
      payId,
      customer,
      amount,
      token,
      updatedAt
    )
    handleIntentUpdated(newIntentUpdatedEvent)
  })

  afterAll(() => {
    clearStore()
  })

  // For more test scenarios, see:
  // https://thegraph.com/docs/en/subgraphs/developing/creating/unit-testing-framework/#write-a-unit-test

  test("IntentUpdated created and stored", () => {
    assert.entityCount("IntentUpdated", 1)

    // 0xa16081f360e3847006db660bae1c6d1b2e17ec2a is the default address used in newMockEvent() function
    assert.fieldEquals(
      "IntentUpdated",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "payId",
      "234"
    )
    assert.fieldEquals(
      "IntentUpdated",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "customer",
      "0x0000000000000000000000000000000000000001"
    )
    assert.fieldEquals(
      "IntentUpdated",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "amount",
      "234"
    )
    assert.fieldEquals(
      "IntentUpdated",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "token",
      "0x0000000000000000000000000000000000000001"
    )
    assert.fieldEquals(
      "IntentUpdated",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "updatedAt",
      "234"
    )

    // More assert options:
    // https://thegraph.com/docs/en/subgraphs/developing/creating/unit-testing-framework/#asserts
  })
})
