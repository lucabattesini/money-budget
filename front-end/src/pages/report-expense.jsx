import { Center, Stack, Button, Heading, Input} from "@chakra-ui/react";

export default function ReportExpense() {
    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="center"
            >
                <Heading>
                    Report Expense
                </Heading>
                <Input placeholder="Amount" variant="outline" />
                <Button>Submit</Button>
            </Stack>
        </Center>
    );
}   