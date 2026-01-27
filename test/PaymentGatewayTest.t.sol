//SPDX-License-Identifier:MIT

pragma solidity 0.8.20;

import {Test} from "../lib/forge-std/src/Test.sol";
import {MockUsdt} from "../src/MockUsdt.sol";
import {OnChainPaymentGateWay} from "../src/OnChainPaymentGateWay.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

contract PaymentGatewayTest is Test {
    OnChainPaymentGateWay ocpg;
    MockUsdt mUsdt;
    MockUsdt mUsdc;
    MockUsdt unregistreredToken;

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
    event Paid(
        uint256 indexed payId,
        uint256 indexed amount,
        uint256 indexed paidAt
    );

    event Paid(uint256 indexed amount, uint256 paidAt);
    address owner = makeAddr("Owner");

    address merchant1 = makeAddr("merchant1");
    address merchant2 = makeAddr("merchant2");
    address customer1 = makeAddr("firstCoustmer");

    uint256 startingAmount = 2e18;
    uint256 expiryDuration = 1 days;

    modifier registerMerchant() {
        // Register Merchant
        vm.startPrank(merchant1);
        vm.expectEmit(true, true, false, true);
        emit MerchantRegistered(merchant1, block.timestamp, "Trader");
        ocpg.registerMerchant("Trader");
        vm.stopPrank();
        _;
    }

    function setUp() external {
        vm.startPrank(owner);
        ocpg = new OnChainPaymentGateWay(owner);
        mUsdt = new MockUsdt("Mock USDT", "mUSDT");
        mUsdc = new MockUsdt("Mock USDC", "mUSDC");
        unregistreredToken = new MockUsdt("Mock UnRegistered", "mUR");

        // enabling token

        vm.expectEmit(true, false, false, false);
        emit TokenEnabled(address(mUsdc));
        ocpg.enableToken(IERC20(mUsdc));

        vm.expectEmit(true, false, false, false);
        emit TokenEnabled(address(mUsdt));
        ocpg.enableToken(IERC20(mUsdt));

        vm.stopPrank();
    }

    function test_EntireFlow() public {
        // Register Merchant
        vm.startPrank(merchant1);
        vm.expectEmit(true, true, false, true);
        emit MerchantRegistered(merchant1, block.timestamp, "Trader");
        ocpg.registerMerchant("Trader");
        vm.stopPrank();

        // Storage variable Changes
        OnChainPaymentGateWay.Merchant memory merchantData = ocpg
            .getMerchantInfo(merchant1);

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

        // Customer will pay the amount

        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectEmit(true, true, true, false);
        emit Paid(1, startingAmount, block.timestamp);
        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));

        // checking storage variable

        OnChainPaymentGateWay.PaymentIntent memory _paymentIntentInfo = ocpg
            .getPaymentIntentInfo(1);

        // changes in storage variable
        assertEq(_paymentIntentInfo.merchant, merchant1);
        assertEq(_paymentIntentInfo.customer, customer1);
        assertEq(_paymentIntentInfo.amount, startingAmount);
        assertEq(_paymentIntentInfo.createdAt, block.timestamp);
        assertEq(address(_paymentIntentInfo.token), address(mUsdc));
        assertEq(
            _paymentIntentInfo.expiryTime,
            block.timestamp + expiryDuration
        );
        assertEq(_paymentIntentInfo.paidAt, block.timestamp);
        assertEq(_paymentIntentInfo.isPaid, true);
        assertEq(_paymentIntentInfo.lastUpdatedAt, block.timestamp);
    }

    /////////////////////////////////////
    /// createPaymentIntent/////////////
    ///////////////////////////////////

    function test_CreatePaymentIntent() public {
        // Register Merchant
        vm.startPrank(merchant1);
        vm.expectEmit(true, true, false, true);
        emit MerchantRegistered(merchant1, block.timestamp, "Trader");
        ocpg.registerMerchant("Trader");
        vm.stopPrank();

        // Storage variable Changes
        OnChainPaymentGateWay.Merchant memory merchantData = ocpg
            .getMerchantInfo(merchant1);

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

    function test_CreatePaymentIntent_NonRegisteredMerchant() public {
        vm.expectRevert(OnChainPaymentGateWay.MerchantNotRegistered.selector);
        ocpg.createPaymentIntent(
            startingAmount,
            customer1,
            expiryDuration,
            IERC20(mUsdc)
        );
    }

    function test_CreatePaymentIntent_Revert_WhenPaused()
        public
        registerMerchant
    {
        vm.startPrank(owner);
        ocpg.pause();
        vm.expectRevert(Pausable.EnforcedPause.selector);
        vm.startPrank(merchant1);
        ocpg.createPaymentIntent(
            startingAmount,
            customer1,
            expiryDuration,
            IERC20(mUsdc)
        );
        vm.stopPrank();
    }

    function test_CreatePaymentIntent_Revert_TokenNotEbnable()
        public
        registerMerchant
    {
        vm.expectRevert(
            OnChainPaymentGateWay.InvalidTokenOrNotEnabled.selector
        );
        vm.startPrank(merchant1);
        ocpg.createPaymentIntent(
            startingAmount,
            customer1,
            expiryDuration,
            IERC20(unregistreredToken)
        );
        vm.stopPrank();
    }

    function test_CreatePaymentIntent_Revert_NonActiveMerchant() public registerMerchant {

        vm.startPrank(owner);
        ocpg.makeMerchantInActive(merchant1);
        vm.stopPrank();

        vm.startPrank(merchant1);
        vm.expectRevert(OnChainPaymentGateWay.MerchantIsInactive.selector);
        ocpg.createPaymentIntent(
            startingAmount,
            customer1,
            expiryDuration,
            IERC20(mUsdc)
        );
        vm.stopPrank();

    }
}
