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

    event IntentUpdated(
        uint256 indexed payId,
        address indexed customer,
        uint256 indexed amount,
        address token,
        uint256 updatedAt
    );
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
        // Storage variable Changes
        OnChainPaymentGateWay.Merchant memory merchantData = ocpg
            .getMerchantInfo(merchant1);

        assertEq(merchantData.businessName, "Trader");
        assertEq(merchantData.registeredAt, block.timestamp);

        assertEq(merchantData.isActive, true);
        _;
    }

    modifier createPaymentIntent() {
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

        _;
    }

    modifier payIntent() {
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

    function test_EntireFlow()
        public
        registerMerchant
        createPaymentIntent
        payIntent
    {}

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

    function test_CreatePaymentIntent_Revert_NonActiveMerchant()
        public
        registerMerchant
    {
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

    /////////////////////////////////////
    /// Update Intent //////////////////
    ///////////////////////////////////

    function test_UpdateIntent() public registerMerchant createPaymentIntent {
        vm.startPrank(merchant1);
        vm.expectEmit(true, true, true, true);
        emit IntentUpdated(
            1,
            address(5),
            5e18,
            address(mUsdt),
            block.timestamp
        );

        ocpg.updateIntent(1, 5e18, IERC20(mUsdt), address(5));

        // checking in storage variable
        OnChainPaymentGateWay.PaymentIntent memory paymentIntentInfo = ocpg
            .getPaymentIntentInfo(1);

        // changes in storage variable
        assertEq(paymentIntentInfo.merchant, merchant1);
        assertEq(paymentIntentInfo.customer, address(5));
        assertEq(paymentIntentInfo.amount, 5e18);
        assertEq(paymentIntentInfo.createdAt, block.timestamp);
        assertEq(address(paymentIntentInfo.token), address(mUsdt));
        assertEq(
            paymentIntentInfo.expiryTime,
            block.timestamp + expiryDuration
        );
        assertEq(paymentIntentInfo.paidAt, 0);
        assertEq(paymentIntentInfo.isPaid, false);
        assertEq(paymentIntentInfo.lastUpdatedAt, block.timestamp);
    }

    function test_UpdateIntent_Revert_MerchantInactive()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(owner);
        ocpg.makeMerchantInActive(merchant1);
        vm.stopPrank();

        vm.startPrank(merchant1);
        vm.expectRevert(OnChainPaymentGateWay.MerchantIsInactive.selector);
        ocpg.updateIntent(1, 5e18, IERC20(mUsdt), address(5));
    }

    function test_UpdateIntent_Recert_TokenNotEnabled()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(merchant1);
        vm.expectRevert(
            OnChainPaymentGateWay.InvalidTokenOrNotEnabled.selector
        );
        ocpg.updateIntent(1, 5e18, IERC20(unregistreredToken), address(5));
    }

    function test_UpdateIntent_Revert_Not_Merchant()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(merchant2);
        vm.expectRevert(OnChainPaymentGateWay.MerchantNotRegistered.selector);
        ocpg.updateIntent(1, 5e18, IERC20(mUsdt), address(5));
    }

    function test_UpdateIntent_Revert_TimePassed()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.warp(block.timestamp + 5 days);
        vm.startPrank(merchant1);
        vm.expectRevert(OnChainPaymentGateWay.TimePassed.selector);
        ocpg.updateIntent(1, 5e18, IERC20(mUsdc), address(5));
    }

    function test_UpdateIntent_Revert_Alreadypaid()
        public
        registerMerchant
        createPaymentIntent
    {
        // coustmer will pay
        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectEmit(true, true, true, false);
        emit Paid(1, startingAmount, block.timestamp);
        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));

        // trying to update after its paid
        vm.startPrank(merchant1);
        vm.expectRevert(OnChainPaymentGateWay.AlreadyPaid.selector);
        ocpg.updateIntent(1, 5e18, IERC20(mUsdc), address(5));
    }

    function test_UpdateIntent_Revert_Paused()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(owner);
        ocpg.pause();
        vm.expectRevert(Pausable.EnforcedPause.selector);
        ocpg.updateIntent(1, 5e18, IERC20(mUsdc), address(5));
    }

    /////////////////////////////////
    // executePayment////////////////
    /////////////////////////////////
    function test_ExecutePayment()
        public
        registerMerchant
        createPaymentIntent
        payIntent
    {}

    function test_ExecutePayment_Revert_WhenPaused()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(owner);
        ocpg.pause();
        vm.stopPrank();

        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(Pausable.EnforcedPause.selector);

        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));
        vm.stopPrank();
    }

    function test_ExecutePayment_Revert_InactiveMerchant()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(owner);
        ocpg.makeMerchantInActive(merchant1);
        vm.stopPrank();

        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(OnChainPaymentGateWay.MerchantIsInactive.selector);

        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));
        vm.stopPrank();
    }

    function test_ExecutePayment_Revert_AlreadyPaid()
        public
        registerMerchant
        createPaymentIntent
        payIntent
    {
        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(OnChainPaymentGateWay.AlreadyPaid.selector);

        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));
        vm.stopPrank();
    }

    function test_ExecutePayment_Revert_InvalidTokenOrNotEnabled()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(OnChainPaymentGateWay.InvalidTokenOrNotEnabled.selector);

        ocpg.executePayment(1, startingAmount, IERC20(unregistreredToken));
        vm.stopPrank();
    }

     function test_ExecutePayment_Revert_RevertAmount_NotEqual()
        public
        registerMerchant
        createPaymentIntent
    {
        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(abi.encodeWithSelector(OnChainPaymentGateWay.InvalidAmount.selector, startingAmount, startingAmount + 1));

        ocpg.executePayment(1, startingAmount + 1, IERC20(mUsdc));
        vm.stopPrank();
    }

    function test_ExecutePayment_Revert_TimePassed()
        public
        registerMerchant
        createPaymentIntent
    {

        vm.warp(block.timestamp+ 5 days);
        vm.startPrank(customer1);
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(OnChainPaymentGateWay.TimePassed.selector);

        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));
        vm.stopPrank();
    }
    function test_ExecutePayment_Revert_OnlySpecificCustomerCanPay()
        public
        registerMerchant
        createPaymentIntent
    {

        vm.startPrank(makeAddr("Differentuser"));
        mUsdc.mint(customer1, startingAmount);
        mUsdc.approve(address(ocpg), startingAmount);

        vm.expectRevert(OnChainPaymentGateWay.OnlyCustomerCanPay.selector);

        ocpg.executePayment(1, startingAmount, IERC20(mUsdc));
        vm.stopPrank();
    }


}
