import { Stack, Center, Heading, Box } from "@chakra-ui/react"

export default function Investments() {
    return(
        <Center>
            <Stack
                minHeight="100vh"
                gap={6}
                w="full"
                maxW="md"
                align="center"
                justify="flex-start"
                py={10}
            >
                <Heading size={"2xl"}>
                    Painel de Investimentos
                </Heading>
                
            </Stack>
        </Center>
    )
}