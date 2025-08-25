import { Stack, Center, Heading } from "@chakra-ui/react"

export default function Investments() {
    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size={"2xl"}>
                    Investments Dashboard
                </Heading>
                
            </Stack>
        </Center>
    )
}