//SPDX-License-Identifier:MIT

pragma solidity 0.8.20;

import {Test} from "../lib/forge-std/src/Test.sol";
import {MockUsdt} from "../src/MockUsdt.sol";
import {OnChainPaymentGateWay} from "../src/OnChainPaymentGateWay.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract PaymentGatewayTest is Test {
    OnChainPaymentGateWay ocpg;
    MockUsdt mUsdt;
    MockUsdt mUsdc;

    event MerchantRegistered(
        address indexed merchant,
        uint256 indexed registeredAt,
        string businessName
    );
    event PaymentIntentCreated(
        uint256 indexed payId,
        address indexed customer,
        uint256 indexed amount,
        address merchant,
        uint256 createdAt,
        uint256 expiryTime
    );

    event TokenEnabled(address indexed _token);
    event TokenDisabled(address indexed _token);

    event Paid(uint256 indexed amount, uint256 paidAt);
    address owner = makeAddr("Owner");

    address merchant1 = makeAddr("merchant1");
    address merchant2 = makeAddr("merchant2");
    address customer1 = makeAddr("firstCoustmer");

    uint256 startingAmount = 2e18;
    uint256 expiryDuration = 1 days;

    function setUp() external {
        vm.startPrank(owner);
        ocpg = new OnChainPaymentGateWay(owner);
        mUsdt = new MockUsdt("Mock USDT", "mUSDT");
        mUsdc = new MockUsdt("Mock USDC", "mUSDC");

        // enabling token

        vm.expectEmit(true, false, false, false);
        emit TokenEnabled(address(mUsdc));
        ocpg.enableToken(IERC20(mUsdc));

        vm.expectEmit(true, false, false, false);
        emit TokenEnabled(address(mUsdt));
        ocpg.enableToken(IERC20(mUsdt));

        vm.stopPrank();
    }

    function test_MerchantRegister() public {
        // Register Merchant
        vm.startPrank(merchant1);
        vm.expectEmit(true, true, false, true);
        emit MerchantRegistered(merchant1, block.timestamp, "Trader");
        ocpg.registerMerchant("Trader");
        vm.stopPrank();

        // Storage variable Changes
        OnChainPaymentGateWay.Merchant memory merchantData = ocpg
            .getMerchantInfo(merchant1);

        assertEq(merchantData.merchant, merchant1);
        assertEq(merchantData.businessName, "Trader");
        assertEq(merchantData.registeredAt, block.timestamp);

        assertEq(merchantData.isActive, true);
        vm.expectEmit(true, true, true, true);
        vm.startPrank(merchant1);
        emit PaymentIntentCreated(
            1,
            customer1,
            startingAmount,
            merchant1,
            block.timestamp,
            block.timestamp + expiryDuration
        );
        ocpg.createPaymentIntent(
            startingAmount,
            customer1,
            expiryDuration,
            IERC20(mUsdc)
        );
        vm.stopPrank();
        OnChainPaymentGateWay.PaymentIntent memory paymentIntentInfo = ocpg
            .getPaymentIntentInfo(1);

        // changes in storage variable
        assertEq(paymentIntentInfo.merchant, merchant1);
        assertEq(paymentIntentInfo.customer, customer1);
        assertEq(paymentIntentInfo.amount, startingAmount);
        assertEq(paymentIntentInfo.createdAt, block.timestamp);
        assertEq(address(paymentIntentInfo.token), address(mUsdc));
        assertEq(
            paymentIntentInfo.expiryTime,
            block.timestamp + expiryDuration
        );
        assertEq(paymentIntentInfo.paidAt, 0);
        assertEq(paymentIntentInfo.isPaid, false);
        assertEq(paymentIntentInfo.lastUpdatedAt, block.timestamp);
    }
}
