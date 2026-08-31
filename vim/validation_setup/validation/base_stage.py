from abc import ABC, abstractmethod

class BaseStage(ABC):

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def validate(self, invoice, context=None):
        """
        Execute validation for an invoice.

        Returns:
            dict containing:
            - stage
            - status
            - message
            - details
        """
        pass