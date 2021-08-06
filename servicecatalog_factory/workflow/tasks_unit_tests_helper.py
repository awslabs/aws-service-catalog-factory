#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import unittest
from unittest import mock


def mocked_client():
    context_handler_mock = mock.MagicMock()
    client_mock = mock.MagicMock()
    context_handler_mock.return_value.__enter__.return_value = client_mock
    return client_mock, context_handler_mock


class FakeInput(object):

    values = None

    def __init__(self) -> None:
        self.values = dict()

    def get_value(self, name):
        return self.values.get(name)

    def set_value(self, name, value):
        self.values[name] = value


class FactoryTaskUnitTest(unittest.TestCase):
    cache_invalidator = "NOW"

    def wire_up_mocks(self):
        self.spoke_client_mock, self.sut.spoke_client = mocked_client()
        (
            self.spoke_regional_client_mock,
            self.sut.spoke_regional_client,
        ) = mocked_client()

        self.hub_client_mock, self.sut.hub_client = mocked_client()
        self.hub_regional_client_mock, self.sut.hub_regional_client = mocked_client()

        self.sut.write_output = mock.MagicMock()
        self.sut.input = mock.MagicMock()

        self.fake_inputs = FakeInput()
        self.sut.read_from_input = self.fake_inputs.get_value

    def assert_client_called_with(
        self,
        spoke_regional_client,
        spoke_regional_client_mock,
        client_used,
        function_name_called,
        function_parameters,
        extra_args={},
    ):
        spoke_regional_client.assert_called_once_with(client_used, **extra_args)

        function_called = getattr(spoke_regional_client_mock, function_name_called)
        function_called.assert_called_once_with(**function_parameters)

    def assert_spoke_regional_client_called_with(
        self, client_used, function_name_called, function_parameters
    ):
        self.assert_client_called_with(
            self.sut.spoke_regional_client,
            self.spoke_regional_client_mock,
            client_used,
            function_name_called,
            function_parameters,
        )

    def assert_hub_regional_client_called_with(
        self, client_used, function_name_called, function_parameters, extra_args={}
    ):
        self.assert_client_called_with(
            self.sut.hub_regional_client,
            self.hub_regional_client_mock,
            client_used,
            function_name_called,
            function_parameters,
            extra_args,
        )

    def inject_client_with_response(self, client, function_name, response):
        f = getattr(client, function_name)
        f.return_value = response

    def inject_hub_regional_client_called_with_response(
        self, client_used, function_name_called, response
    ):
        self.inject_client_with_response(
            self.hub_regional_client_mock, function_name_called, response
        )

    def inject_spoke_regional_client_called_with_response(
        self, client_used, function_name_called, response
    ):
        self.inject_client_with_response(
            self.spoke_regional_client_mock, function_name_called, response
        )

    def inject_into_input(self, name, value):
        self.fake_inputs.set_value(name, value)

    def assert_output(self, expected_output):
        self.sut.write_output.assert_called_once_with(expected_output)
