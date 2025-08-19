import { Center, Stack, Input, Button, Heading } from "@chakra-ui/react";

export default function CreateAccount() {
    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading>Create account</Heading>

                <Input placeholder="First name" variant="outline"/>
                <Input placeholder="Last name" variant="outline"/>
                <Input placeholder="Email address" variant="outline"/>
                <Input placeholder="Password" variant="outline"/>

                <Button>Sign In</Button>
            </Stack>
        </Center>
    );
}